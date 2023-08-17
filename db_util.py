from bson.objectid import ObjectId
from pymongo import MongoClient
import random
import os
import string
import dropbox


class Clients:

    """
        Holds MongoDB client URLs and generic functions not related to any course. 
        This is specific for a session - that is, a teacher.
    """

    def __init__(self, students, teachers, courses):
        self.students = students
        self.teachers = teachers
        self.courses = courses

    def add_email(self, email):
        self.email = email

    def generate_token(self) -> str:
        """
            Generate a unique 8-digit token that has not been assigned to any teacher yet.
            :returns `token`: 8-digit token in string format
        """

        token = ''.join(random.choices(string.digits, k=8))

        unique = False
        while not unique:
            if not self.teachers.find_one({'token': token}):
                unique = True
            else:
                token = ''.join(random.choices(string.digits, k=8))

        return token

    def get_courses(self) -> list:
        """
            Get the courses taught by a teacher.
            :return `user_courses`: List of dicts, each describing a course
        """
        user_courses = []

        # get course ids of the courses
        course_ids = self.teachers.find_one(
            {"email": self.email})["courses"]

        for course_object_id in course_ids:
            course = self.courses.find_one({"_id": ObjectId(course_object_id)})
            course.pop("_id")
            user_courses.append(course)
        return user_courses


class Database:

    """
        Holds context for one single course, for one batch for that particular teacher.
        # TODO: name can probably be changed to something more apt
    """

    def __init__(self, clients: Clients, course_id: str, batch: str):
        self.students = clients.students
        self.teachers = clients.teachers
        self.courses = clients.courses
        self.email = clients.email

        self.course_id = course_id
        self.batch = batch

    def authorised_for_course(self):
        """
            Check if the given teacher is authorised to edit the given course.
            :return `True` if authorised, an error string if not.
        """

        if self.get_course_object_id() not in self.teachers.find_one({"email": self.email})['courses']:
            return 'You cannot delete this course as you are not its owner.'

        return True

    def get_course_object_id(self) -> str:
        """
            Get the unique object ID assigned by MongoDB to a course.
            :return `course_object_id`: the unique object ID
        """

        course_object_id = str(self.courses.find_one({
            'course_id': self.course_id,
            'batch': self.batch
        })['_id'])

        return course_object_id

    def course_exists(self):
        """
            Check if a given course exists within the database.
            :return `True` if exists, an error string if not.
        """

        course = self.courses.find_one({
            'course_id': self.course_id,
            'batch': self.batch
        })

        if course is None:
            return 'Course does not exist!'

        return True

    def save_file_dropbox(self, file_path: str, file_name: str):
        """
            Upload user input files to Dropbox in the user folder.
            :param file_path: File path from where the file has to be taken
            :param courses: File name
        """
        access_token = os.getenv('DROPBOX_ACCESS_TOKEN')

        # destination folder and file path
        dest = f'/{self.email}/{file_name}'
        dbx = dropbox.Dropbox(
            app_key=os.getenv("DROPBOX_APP_KEY"),
            app_secret=os.getenv("DROPBOX_APP_SECRET"),
            oauth2_refresh_token=os.getenv("DROPBOX_REFRESH_TOKEN")
        )

        with open(file_path, 'rb') as f:
            dbx.files_upload(f.read(), dest, autorename=True)

    def get_name(self, key: str) -> str:
        """
            Get name of the student whose roll number is `key`.
            :return `student`: Name of the student
        """
        student = self.students.find_one({
            'roll': key
        })
        student.pop('_id')
        return student

    def get_course(self) -> dict:
        """
            Get a course from MongoDB.
            :return `course`: MongoDB result minus the id
        """
        course = self.courses.find_one(
            {'course_id': self.course_id, 'batch': self.batch}
        )

        course.pop('_id')

        return course

    def delete_course(self):
        """
            Remove the course ObjectId from the teacher's records and delete the course.
        """

        self.teachers.update_one({
            "email": self.email
        }, {
            '$pull': {
                'courses': self.get_course_object_id()
            }
        })

        result = self.courses.delete_one({
            'course_id': self.course_id,
            'batch': self.batch
        })

    def update_course_after_parse(self, course_students: list, students: list, flagged: list, dates: list, count: int):
        """
            Updates the course with student records & dates
            :param `course_students`: List of roll numbers of students enrolled in the course
            :param `students`: List of list of tuples returned by parsing functions
            :param `flagged`: List of list of roll numbers to be flagged
            :param `date`: List of dates for which attendance is being tracked
            :param `count`: Number of dates for which update is being made
        """

        set_query = {}

        for student_id in course_students:

            for index in range(count):

                status = False

                # if the student has a record in the uploaded file and has not been flagged

                if (student_id in students[index].keys()) and (student_id not in flagged[index]):
                    status = students[index][student_id][1]

                query_key = f'students.{student_id}.{dates[index]}'
                set_query[query_key] = status

        self.courses.update_one({
            'course_id': self.course_id,
            'batch': self.batch
        }, {
            # '$set': {
            #     f'students.{student_id}.{date}': status
            # }
            '$set': set_query
        })

        # add this date to the dates that have been tracked for this course
        self.courses.update_one({
            'course_id': self.course_id,
            'batch': self.batch}, {
                '$push': {
                    'dates': {
                        '$each': dates
                    }
                }
        })
