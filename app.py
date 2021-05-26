import json
import os
import random
import string
from uuid import uuid4

from bson.objectid import ObjectId
from dateutil import parser
from flask import Flask
from flask import jsonify
from flask import make_response
from flask import redirect
from flask import render_template
from flask import request
from flask import send_from_directory
from flask import session
from flask import url_for
from flask_cors import CORS
from flask_cors import cross_origin
from pymongo import MongoClient

from db_util import Clients
from db_util import Database
from decorators import login_required
from decorators import misc_error
from file_util import attribute_check
from file_util import GoogleFormFile
from file_util import remove_whitespaces
from file_util import Report
from file_util import StudentFile
from file_util import TeamsFile
from file_util import UploadedFile

app = Flask(__name__, template_folder="templates", static_url_path="/static")
app.secret_key = "lol"
cors = CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"
app.config["UPLOAD_FOLDER"] = "./files"

client = MongoClient(os.getenv("MONGO_DB_URL"))
teachers = client["attendance-website"]["teacher"]
courses = client["attendance-website"]["course"]
students = client["attendance-website"]["student"]

client_obj = Clients(students, teachers, courses)

if __name__ == "__main__":
    app.run(host="0.0.0.0")


def get_user_email(data: dict) -> str:
    """
    Get the email of the user based on whether the user is from the app or the API.
    Includes check for missing token if API user.
    """
    if data["api"] == "0":
        return session["user"]["email"]

    else:
        if data["token"] == "":
            print("Token is empty!!!")

        person = teachers.find_one({"token": data["token"]})
        return person["email"]


@app.route("/get_all_courses", methods=["POST"])
@cross_origin()
def get_all_courses():

    all_courses = client_obj.get_courses()
    return make_response(jsonify({"courses": all_courses}), 200)


@app.route("/")
def index():

    # empty the upload folder directory
    for root, dirs, files in os.walk(app.config["UPLOAD_FOLDER"]):
        for file in files:
            os.remove(os.path.join(root, file))

    # redirect to sign-in page if not logged in
    if "user" not in session.keys():
        return render_template("index.html", message="", logged_in=False)

    # open home page if logged in
    else:
        client_obj.add_email(session["user"]["email"])
        return render_template(
            "home.html",
            # pass the username of the current user
            username=session["user"]["name"],
            # pass all the courses of the current user
            courses=client_obj.get_courses(),
            logged_in=True,
        )


@app.route("/upload_attendance", methods=["POST"])
@cross_origin()
def upload_attendance():

    try:
        form_data = request.form.to_dict()
    except:
        return make_response(
            jsonify({"error": "This route only accepts a FormData object."}), 400
        )

    form_data = remove_whitespaces(form_data)

    db_obj = Database(client_obj, form_data["course_id"], form_data["batch"])

    file_obj = ""
    dates = []
    files = request.files.getlist("file")
    for file in files:

        file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(file_path)

        # upload the file to dropbox
        db_obj.save_file_dropbox(file_path, file.filename)

        filename, extension = file.filename.split(".")

        generic_file_obj = UploadedFile(file_path, file.filename, db_obj)

        students = {}

        check_extension_result = generic_file_obj.check_extension()
        if check_extension_result != True:
            return make_response(jsonify({"error": check_extension_result}), 400)

        if extension != "csv":

            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename + ".csv")
            generic_file_obj.convert_to_csv(result_path=file_path)
            generic_file_obj.file_path = file_path

        file_type = generic_file_obj.get_file_type()

        if form_data["upload_type"] == "0":
            if form_data["input_mode"] == "0":

                if file_type != 0:
                    return make_response(
                        jsonify(
                            {
                                "error": "The report you have uploaded does not conform to the format for Google Form."
                            }
                        ),
                        400,
                    )

                file_obj = GoogleFormFile(file_path, file.filename, db_obj)

            else:

                if file_type != 1:
                    return make_response(
                        jsonify(
                            {
                                "error": "The report you have uploaded does not conform to the format for MS Teams."
                            }
                        ),
                        400,
                    )
                file_obj = TeamsFile(file_path, file.filename, db_obj)

        else:

            if file_type == 0:
                file_obj = GoogleFormFile(file_path, file.filename, db_obj)

            elif file_type == 1:
                file_obj = TeamsFile(file_path, file.filename, db_obj)

            else:
                return make_response(
                    jsonify(
                        {
                            "error": "Report(s) uploaded do not conform to either formats - Google Form or MS Teams."
                        }
                    ),
                    400,
                )

            form_data["flags"] = ""

        date, status = file_obj.get_date()
        if status is False:
            return make_response(jsonify({"error": date}), 400)

        flagged = [x.strip() for x in form_data["flags"].split(",")]
        if "" in flagged:
            flagged.remove("")

        if file_type == 0:
            students = file_obj.parse_google_form_result(file_path)

        elif file_type == 1:

            if form_data["upload_type"] == "1":
                end_time = f"{date}, 11:59 PM"
                threshold = 0

            else:

                end_time = form_data["end-time"]
                threshold = int(form_data["threshold"])

                if date != str(parser.parse(end_time, dayfirst=True).date()):

                    return make_response(
                        jsonify(
                            {
                                "error": "Different dates present in File and Meeting End Time"
                            }
                        ),
                        400,
                    )

            students = file_obj.parse_downloaded_report(end_time, threshold, file_path)

        if isinstance(students, str):
            return make_response(jsonify({"error": students}), 400)

        # remove the uploaded file
        os.remove(file_path)

        course = db_obj.get_course()

        if date in course["dates"]:
            return make_response(
                jsonify(
                    {"error": "Attendance for this date has already been recorded."}
                ),
                400,
            )

        course_students = course["students"].keys()

        for roll in students.keys():
            if roll not in course_students:
                return make_response(
                    jsonify(
                        {
                            "error": f"Roll {roll} mentioned in the report has not been added to this course."
                        }
                    ),
                    400,
                )

        # check if flagged students are enrolled in the course
        if len(flagged) > 0:
            for roll in flagged:
                if roll not in course_students:
                    return make_response(
                        jsonify(
                            {
                                "error": f"Roll {roll} mentioned in the flags has not been added to this course."
                            }
                        ),
                        400,
                    )

        # update every student and the course

        db_obj.update_course_after_parse(course_students, students, flagged, date)

        dates.append(date)

    success_message = "Attendance updated for the following: "
    for date in dates:
        success_message += date + ", "
    return make_response(jsonify({"message": success_message}), 200)


@app.route("/download_attendance", methods=["POST"])
@cross_origin()
def download_attendance():

    course_id, batch = request.form.get("down-course").split("-")

    db_obj = Database(client_obj, course_id, batch)

    # check if course exists
    course_existence = db_obj.course_exists()
    if course_existence == False:
        return make_response(jsonify({"error": "This course does not exist"}), 400)

    report_obj = Report(
        app.config["UPLOAD_FOLDER"],
        db_obj,
        int(request.form.get("report_type")),
        int(request.form.get("report_format")),
    )

    # create the attendance report based on passed parameters
    filename, status = report_obj.make_report()

    if status == False:
        return make_response(jsonify({"error": filename}), 401)

    # send the created report
    return send_from_directory(
        app.config["UPLOAD_FOLDER"], filename, as_attachment=True
    )


@app.route("/delete_course", methods=["POST"])
@cross_origin()
def delete_course():
    try:
        form_data = request.form.to_dict()
    except:
        return make_response(
            jsonify({"error": "This route only accepts a FormData object."}), 400
        )

    form_data = remove_whitespaces(form_data)

    # check if all the attributes based in the FormData object are okay
    attribute_check_result = attribute_check(
        ["course_id", "batch"], form_data, extras=["course"]
    )
    if attribute_check_result != True:
        return make_response(jsonify({"error": attribute_check_result}), 400)

    db_obj = Database(client_obj, form_data["course_id"], form_data["batch"])

    # check if the teacher is authorised to edit this course
    authorised_check_result = db_obj.authorised_for_course()
    if authorised_check_result != True:
        return make_response(jsonify({"error": authorised_check_result}), 400)

    # check if the course exists
    course_existence = db_obj.course_exists()
    if course_existence == False:
        return make_response(jsonify({"error": "This course does not exist."}), 400)

    db_obj.delete_course()

    return make_response(jsonify({"message": "yes"}), 200)


@app.route("/add_course", methods=["POST"])
@cross_origin()
def add_course():

    try:
        form_data = request.form.to_dict()
    except:
        return make_response(
            jsonify({"error": "This route only accepts a FormData object."}), 400
        )

    form_data = remove_whitespaces(form_data)

    # check if all the attributes based in the FormData object are okay
    attribute_check_result = attribute_check(
        ["course_id", "course_name", "batch"], form_data
    )
    if attribute_check_result != True:
        return make_response(jsonify({"error": attribute_check_result}), 400)

    db_obj = Database(client_obj, form_data["course_id"], form_data["batch"])

    # check if course exists
    course_existence = db_obj.course_exists()
    if course_existence == True:
        return make_response(
            jsonify(
                {"error": "A course with this Course ID for this batch already exists."}
            ),
            400,
        )

    if form_data["batch"] < "0":
        return make_response(
            jsonify({"error": "Negative batch year is not permissible."}), 400
        )

    # save the uploaded course file
    file = request.files.get("file")
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)

    file_obj = StudentFile(file_path, file.filename, db_obj)

    filename_check = file_obj.check_extension()
    if filename_check != True:
        return make_response(jsonify({"error": filename_check}), 400)

    # get extracted student details from the course file
    course_students = file_obj.get_students_from_file()
    if isinstance(course_students, str):
        return make_response(jsonify({"error": course_students}), 400)

    form_data["students"] = {}

    # insert students into the DB
    for student in course_students:

        # skip students already having a record
        existing = students.find_one({"roll": student[0]})

        if existing is None:
            inserted_student = students.insert_one(
                {"roll": student[0], "name": student[1], "batch": form_data["batch"]}
            )

        # add the student roll number to the course data
        form_data["students"][student[0]] = {}

    form_data["dates"] = []

    # remove the uploaded file
    os.remove(file_path)

    # prepare data to pass to get the user email
    # data_dict = {}
    # api = form_data.pop('api')
    # data_dict['api'] = api
    # if api == '1':
    #     token = form_data.pop('token')
    #     data_dict['token'] = token

    # insert the course data
    courses.insert_one(form_data)
    form_data.pop("_id")

    # add the course ID to the teacher's data
    teachers.update_one(
        {"email": session["user"]["email"]},
        {"$addToSet": {"courses": db_obj.get_course_object_id()}},
    )
    return make_response(jsonify({"course": form_data}), 200)


@app.route("/api_signup", methods=["POST"])
def api_signup():

    try:
        form_data = request.form.to_dict()
    except:
        return make_response(
            jsonify({"error": "This route only accepts a FormData object."}), 400
        )

    form_data = remove_whitespaces(form_data)

    # check if all the attributes based in the FormData object are okay
    attribute_check_result = attribute_check(["name", "email", "password"], form_data)
    if attribute_check_result != True:
        return make_response(jsonify({"error": attribute_check_result}), 400)

    # check if the user has already registered before
    user = teachers.find_one({"email": request.form.get("email")})
    if user != None:
        return make_response(
            jsonify(
                {
                    "error": "A user with this email has already registered with this API."
                }
            )
        )

    # generate a unique token for this new user
    form_data["token"] = client_obj.generate_token(teachers)
    form_data["courses"] = []

    # insert the teacher's data into the DB
    teachers.insert_one(form_data)
    form_data.pop("_id")

    return make_response(jsonify({"token": form_data["token"]}), 200)


@app.route("/help")
def help():
    return render_template("help.html")


@app.route("/login", methods=["POST"])
def login():

    email = request.form.get("email")
    password = request.form.get("password")
    message = ""

    user = teachers.find_one({"email": email})

    # if user exists
    if user != None:

        # if password matches, login
        if password == user["password"]:
            user.pop("_id")
            session["user"] = user
            client_obj.add_email(email)
            return redirect(url_for(".index"))

        else:
            message = "Incorrect password."

    # if user does not exist, ask to signup
    else:
        message = "Not registered. Please sign up."

    client_obj.add_email(email)
    return render_template("index.html", message=message, logged_in=False)


@app.route("/signup", methods=["POST"])
def signup():

    # checking if person had previously registered
    user = teachers.find_one({"email": request.form.get("email")})
    if user != None:
        message = "User already registered. Please log in."
        return render_template("index.html", message=message, logged_in=False)

    credentials = {
        "name": request.form.get("name"),
        "email": request.form.get("email"),
        "password": request.form.get("password"),
        "courses": [],
    }

    # inserting into database
    teachers.insert_one(credentials)
    credentials.pop("_id")

    # logging in
    session["user"] = credentials
    client_obj.add_email(request.form.get("email"))
    return redirect(url_for(".index"))


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for(".index"))
