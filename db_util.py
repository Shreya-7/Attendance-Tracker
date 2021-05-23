from bson.objectid import ObjectId
from pymongo import MongoClient
import random
import os
import string
import dropbox


def generate_token(teachers: MongoClient) -> str:
    """
        Generate a unique 8-digit token that has not been assigned to any teacher yet.
        :param teachers: MongoClient to access the teachers DB to ensure uniqueness
        :return token: 8-digit token in string format
    """

    token = ''.join(random.choices(string.digits, k=8))

    unique = False
    while not unique:
        if not teachers.find_one({'token': token}):
            unique = True
        else:
            token = ''.join(random.choices(string.digits, k=8))

    return token


def authorised_for_course(course_id: str, batch: int, email: str, teachers: MongoClient, courses: MongoClient):
    """
        Check if the given teacher is authorised to edit the given course.
        :param course_id: ID of the course
        :param batch: Starting year of the course batch
        :param email: Teacher email
        :param teachers: MongoClient to access teachers DB
        :param courses: MongoClient to access courses DB
    """

    if get_course_object_id(course_id, batch, courses) not in teachers.find_one({"email": email})['courses']:
        return 'You cannot delete this course as you are not its owner.'

    return True


def get_course_object_id(course_id: str, batch: int, courses: MongoClient) -> str:
    """
        Get the unique object ID assigned by MongoDB to a course.
        :param course_id: ID of the course
        :param batch: Starting year of the course batch
        :param courses: MongoClient to access courses DB
        :return str: the unique object ID
    """

    course_object_id = str(courses.find_one({
        'course_id': course_id,
        'batch': batch
    })['_id'])

    return course_object_id


def course_exists(course_id: str, batch: int, courses: MongoClient):
    """
        Check if a given course exists within the database.

        :param course_id: ID of the course
        :param batch: Starting year of the course batch
        :param courses: MongoClient to access the courses DB
    """

    course = courses.find_one({
        'course_id': course_id,
        'batch': batch
    })

    if course is None:
        return 'Course does not exist!'

    return True


def get_courses(email: str, teachers: MongoClient, courses: MongoClient) -> list:
    """
        Get the courses taught by a teacher.

        :param email: Teacher email
        :param teachers: MongoClient to access teachers DB
        :param courses: MongoClient to access courses DB
        :return user_courses: List of dicts, each describing a course
    """
    user_courses = []

    # get course ids of the courses
    course_ids = teachers.find_one(
        {"email": email})["courses"]

    for course_object_id in course_ids:
        course = courses.find_one({"_id": ObjectId(course_object_id)})
        course.pop("_id")
        user_courses.append(course)
    return user_courses


def save_file_dropbox(email: str, file_path: str, file_name: str):
    """
        Upload user input files to Dropbox in the user folder.

        :param email: Teacher email - used as user folder name
        :param file_path: File path from where the file has to be taken
        :param courses: File name
    """
    access_token = os.getenv('DROPBOX_ACCESS_TOKEN')

    # destination folder and file path
    dest = f'/{email}/{file_name}'
    dbx = dropbox.Dropbox(access_token)

    with open(file_path, 'rb') as f:
        dbx.files_upload(f.read(), dest, autorename=True)
