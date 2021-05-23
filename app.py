from flask import Flask, render_template, request, redirect, session, url_for, jsonify, make_response, send_from_directory
from flask_cors import CORS, cross_origin
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
import json
import random
import string

from dateutil import parser
from uuid import uuid4

from file_util import get_students_from_file, convert_to_csv, make_report, remove_whitespaces, attribute_check, parse_downloaded_report, parse_google_form_result
from db_util import get_courses, generate_token, course_exists, authorised_for_course, get_course_object_id, save_file_dropbox
from decorators import login_required, misc_error

app = Flask(__name__, template_folder='templates', static_url_path='/static')
app.secret_key = "lol"
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config["UPLOAD_FOLDER"] = "./files"

client = MongoClient(os.getenv('MONGO_DB_URL'))
teachers = client["attendance-website"]["teacher"]
courses = client["attendance-website"]["course"]
students = client["attendance-website"]["student"]

if __name__ == '__main__':
    app.run(host='0.0.0.0')


def get_user_email(data: dict) -> str:
    """
        Get the email of the user based on whether the user is from the app or the API.
        Includes check for missing token if API user.
    """
    if data['api'] == '0':
        return session['user']['email']

    else:
        if data['token'] == '':
            print('Token is empty!!!')

        person = teachers.find_one({
            'token': data['token']
        })
        return person['email']


@app.route("/get_all_courses", methods=['POST'])
@cross_origin()
def get_all_courses():

    all_courses = get_courses(get_user_email(
        json.loads(request.data)), teachers, courses)
    return make_response(jsonify({
        'courses': all_courses
    }), 200)


@app.route("/")
def index():

    # empty the upload folder directory
    for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
        for file in files:
            os.remove(os.path.join(root, file))

    # redirect to sign-in page if not logged in
    if "user" not in session.keys():
        return render_template('index.html', message="", logged_in=False)

    # open home page if logged in
    else:
        return render_template(
            'home.html',
            # pass the username of the current user
            username=session["user"]["name"],
            # pass all the courses of the current user
            courses=get_courses(session['user']['email'], teachers, courses),
            logged_in=True)


@app.route("/upload_attendance", methods=['POST'])
@cross_origin()
def upload_attendance():

    try:
        form_data = request.form.to_dict()
    except:
        return make_response(jsonify({
            'error': 'This route only accepts a FormData object.'
        }), 400)

    form_data = remove_whitespaces(form_data)

    # check if all the attributes based in the FormData object are okay
    attributes = ['course_id', 'batch', 'date', 'input_mode']

    # add attributes based on input type
    if form_data['input_mode'] == '1':
        attributes += ['end-time', 'threshold']
    attribute_check_result = attribute_check(
        attributes, form_data, extras=['flags', 'course'])
    if attribute_check_result != True:
        return make_response(jsonify({
            'error': attribute_check_result
        }), 400)

    # check if the teacher is authorised to edit this course
    authorised_check_result = authorised_for_course(
        form_data['course_id'], form_data['batch'], get_user_email(form_data), teachers, courses)
    if authorised_check_result != True:
        return make_response(jsonify({
            'error': authorised_check_result
        }), 400)

    # check if this course exists
    course_existence = course_exists(
        form_data['course_id'], form_data['batch'], courses)
    if course_existence == False:
        return make_response(jsonify({
            'error': 'This course does not exist'
        }), 400)

    # save the uploaded attendance file
    file = request.files.get('file')
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    filename, extension = file.filename.split('.')

    # if the uploaded file is in XLSX format, convert to CSV, save & delete old file
    if extension != 'csv':
        convert_to_csv(file_path)
        os.remove(file_path)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], "Test.csv")

    flagged = [x.strip() for x in form_data['flags'].split(',')]
    if '' in flagged:
        flagged.remove('')
    date = form_data['date']

    if form_data['input_mode'] == '1' and date != str(parser.parse(form_data['end-time'], dayfirst=True).date()):

        return make_response(jsonify({
            'error': 'Different dates given for Attendance Date and Meeting End Time'
        }), 400)

    # get extracted student data from the file

    if form_data['input_mode'] == '0':
        students = parse_google_form_result(form_data['date'], file_path)
    else:
        students = parse_downloaded_report(form_data['end-time'],
                                           int(form_data['threshold']), file_path)

    if isinstance(students, str):
        return make_response(jsonify({
            'error': students
        }), 400)

    # upload the file to dropbox
    save_file_dropbox(get_user_email(form_data), file_path, file.filename)

    # remove the uploaded file
    os.remove(file_path)

    course = courses.find_one(
        {'course_id': form_data['course_id'], 'batch': form_data['batch']})

    if date in course['dates']:
        return make_response(jsonify({
            'error': 'Attendance for this date has already been recorded.'
        }), 400)

    course_students = course['students'].keys()

    for roll in students.keys():
        if roll not in course_students:
            return make_response(jsonify({
                'error': f'Roll {roll} mentioned in the report has not been added to this course.'
            }), 400)

    # check if flagged students are enrolled in the course
    if len(flagged) > 0:
        for roll in flagged:
            if roll not in course_students:
                return make_response(jsonify({
                    'error': f'Roll {roll} mentioned in the flags has not been added to this course.'
                }), 400)

    # update every student

    for student_id in course_students:

        status = False

        # if the student has a record in the uploaded file and has not been flagged

        if (student_id in students.keys()) and (student_id not in flagged):
            status = students[student_id][1]

        courses.update_one({
            'course_id': form_data['course_id'],
            'batch': form_data['batch']
        }, {
            '$set': {
                f'students.{student_id}.{date}': status
            }
        })

    # add this date to the dates that have been tracked for this course
    courses.update_one({
        'course_id': form_data['course_id'],
        'batch': form_data['batch']}, {
            '$push': {
                'dates': date
            }
    })

    return make_response(jsonify({
        'message': 'Godspeed.'
    }), 200)


@ app.route("/download_attendance", methods=['POST'])
@cross_origin()
def download_attendance():

    course_id, batch = request.form.get('down-course').split('-')

    # check if course exists
    course_existence = course_exists(course_id, batch, courses)
    if course_existence == False:
        return make_response(jsonify({
            'error': 'This course does not exist'
        }), 400)

    # create the attendance report based on passed parameters
    filename, status = make_report(
        courses.find_one(
            {'course_id': course_id, 'batch': batch}
        ),
        app.config['UPLOAD_FOLDER'],
        int(request.form.get('report_type')),
        int(request.form.get('report_format')))

    if status == False:
        return make_response(jsonify({
            'error': filename
        }), 401)

    # send the created report
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


@app.route('/delete_course', methods=['POST'])
@cross_origin()
def delete_course():
    try:
        form_data = request.form.to_dict()
    except:
        return make_response(jsonify({
            'error': 'This route only accepts a FormData object.'
        }), 400)

    form_data = remove_whitespaces(form_data)

    # check if all the attributes based in the FormData object are okay
    attribute_check_result = attribute_check(
        ['course_id', 'batch'], form_data, extras=['course'])
    if attribute_check_result != True:
        return make_response(jsonify({
            'error': attribute_check_result
        }), 400)

    # check if the teacher is authorised to edit this course
    authorised_check_result = authorised_for_course(
        form_data['course_id'], form_data['batch'], get_user_email(form_data), teachers, courses)
    if authorised_check_result != True:
        return make_response(jsonify({
            'error': authorised_check_result
        }), 400)

    # check if the course exists
    course_existence = course_exists(
        form_data['course_id'], form_data['batch'], courses)
    if course_existence == False:
        return make_response(jsonify({
            'error': 'This course does not exist.'
        }), 400)

    # remove course ID from the teacher's data
    teachers.update_one({
        "email": get_user_email(form_data)
    }, {
        '$pull': {
            'courses': get_course_object_id(form_data['course_id'], form_data['batch'], courses)
        }
    })

    # remove the course
    result = courses.delete_one({
        'course_id': form_data['course_id'],
        'batch': form_data['batch']
    })

    print(result.deleted_count)

    return make_response(jsonify({
        'message': 'yes'
    }), 200)


@ app.route("/add_course", methods=['POST'])
@ cross_origin()
def add_course():

    try:
        form_data = request.form.to_dict()
    except:
        return make_response(jsonify({
            'error': 'This route only accepts a FormData object.'
        }), 400)

    form_data = remove_whitespaces(form_data)

    # check if all the attributes based in the FormData object are okay
    attribute_check_result = attribute_check(
        ['course_id', 'course_name', 'batch'], form_data)
    if attribute_check_result != True:
        return make_response(jsonify({
            'error': attribute_check_result
        }), 400)

    # check if course exists
    course_existence = course_exists(
        form_data['course_id'], form_data['batch'], courses)
    if course_existence == True:
        return make_response(jsonify({
            'error': 'A course with this Course ID for this batch already exists.'
        }), 400)

    if form_data['batch'] < '0':
        return make_response(jsonify({
            'error': 'Negative batch year? Really?'
        }), 400)

    # save the uploaded course file
    file = request.files.get('file')
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    # get extracted student details from the course file
    course_students = get_students_from_file(file_path)
    if isinstance(course_students, str):
        return make_response(jsonify({
            'error': course_students
        }), 400)

    form_data['students'] = {}

    # insert students into the DB
    for student in course_students:

        # skip students already having a record
        existing = students.find_one({'roll': student[0]})

        if existing is None:
            inserted_student = students.insert_one({
                'roll': student[0],
                'name': student[1],
                'batch': form_data['batch']
            })

        # add the student roll number to the course data
        form_data['students'][student[0]] = {}

    form_data['dates'] = []

    # remove the uploaded file
    os.remove(file_path)

    # prepare data to pass to get the user email
    data_dict = {}
    api = form_data.pop('api')
    data_dict['api'] = api
    if api == '1':
        token = form_data.pop('token')
        data_dict['token'] = token

    # insert the course data
    courses.insert_one(form_data)
    form_data.pop('_id')

    # add the course ID to the teacher's data
    teachers.update_one({"email": get_user_email(data_dict)},
                        {"$addToSet": {
                            "courses": get_course_object_id(
                                form_data['course_id'], form_data['batch'], courses
                            )}
                         })
    return make_response(jsonify({
        'course': form_data
    }), 200)


@app.route("/api_signup", methods=['POST'])
def api_signup():

    try:
        form_data = request.form.to_dict()
    except:
        return make_response(jsonify({
            'error': 'This route only accepts a FormData object.'
        }), 400)

    form_data = remove_whitespaces(form_data)

    # check if all the attributes based in the FormData object are okay
    attribute_check_result = attribute_check(
        ['name', 'email', 'password'], form_data)
    if attribute_check_result != True:
        return make_response(jsonify({
            'error': attribute_check_result
        }), 400)

    # check if the user has already registered before
    user = teachers.find_one({"email": request.form.get("email")})
    if(user != None):
        return make_response(jsonify({
            'error': 'A user with this email has already registered with this API.'
        }))

    # generate a unique token for this new user
    form_data['token'] = generate_token(teachers)
    form_data['courses'] = []

    # insert the teacher's data into the DB
    teachers.insert_one(form_data)
    form_data.pop('_id')

    return make_response(jsonify({
        'token': form_data['token']
    }), 200)


@app.route("/help")
def help():
    return render_template('help.html')


@ app.route("/login", methods=["POST"])
def login():

    email = request.form.get("email")
    password = request.form.get("password")
    message = ""

    user = teachers.find_one({"email": email})

    # if user exists
    if(user != None):

        # if password matches, login
        if(password == user["password"]):
            user.pop('_id')
            session["user"] = user
            return redirect(url_for('.index'))

        else:
            message = "Incorrect password."

    # if user does not exist, ask to signup
    else:
        message = "Not registered. Please sign up."
    return render_template("index.html", message=message, logged_in=False)


@ app.route("/signup", methods=["POST"])
def signup():

    # checking if person had previously registered
    user = teachers.find_one({"email": request.form.get("email")})
    if(user != None):
        message = "User already registered. Please log in."
        return render_template("index.html", message=message, logged_in=False)

    credentials = {
        "name": request.form.get("name"),
        "email": request.form.get("email"),
        "password": request.form.get("password"),
        "courses": []
    }

    # inserting into database
    teachers.insert_one(credentials)
    credentials.pop('_id')

    # logging in
    session["user"] = credentials
    return redirect(url_for('.index'))


@ app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for('.index'))
