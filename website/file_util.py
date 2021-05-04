import csv
import openpyxl
import pandas as pd

from dateutil import parser


def get_students_from_file(file_path: str) -> list:
    """
        Extract student details from the given filepath. Includes checks for correct headings.
        :return: List of tuples of (student roll, student name)
    """
    students = []
    with open(file_path, mode='r') as csv_file:

        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0

        for row in csv_reader:

            if line_count == 0:  # the heading row

                head = row
                if ('Roll Number' not in head) or ('Name' not in head):
                    return 'The row headings should be Roll Number and Name :/'

                # track index so that Name, Roll and Roll, Name both formats are accepted
                roll_index, name_index = head.index(
                    'Roll Number'), head.index('Name')

            else:

                roll, name = row[roll_index], row[name_index]
                students.append((roll, name))

            line_count += 1

    return students


def convert_to_csv(filepath: str):
    """
        Convert given CSV/XLSX file at filepath to a CSV file named Test.csv saved in the 
        files folder.
    """

    excel = openpyxl.load_workbook(filepath)
    sheet = excel.active
    col = csv.writer(open("files/Test.csv", 'w', newline=""))

    for r in sheet.rows:
        col.writerow([cell.value for cell in r])


def parse_google_form_result(date: str, file_path="files/Test.csv") -> dict:
    """
        Parse given CSV attendance file for the Google Forms report. 
        Includes checks for headings, different timestamps & empty student list.

        :param date: The meeting date
        :return students: Dictionary with student roll number (as given in the file) as key
        and tuple (date, Boolean) as value
    """

    students = {}
    with open(file_path, mode='r') as csv_file:

        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0

        # process the file

        for row in csv_reader:
            if line_count == 0:  # heading row

                if row != ['Timestamp', 'Username', 'Your Name', 'Your Roll Number']:
                    return 'Wrong headings'

                # find indexes so that column exchange is permitted
                roll_index = row.index('Your Roll Number')
                timestamp_index = row.index('Timestamp')

            else:

                student_id = str(int(row[roll_index].split('.')[0]))
                timestamp = parser.parse(row[timestamp_index], dayfirst=True)

                extracted_date = timestamp.date()  # extract date
                print(extracted_date, date)

                # check to see if all dates in the file are consistent
                if extracted_date != parser.parse(date, dayfirst=True).date():

                    return 'Different dates. Wut.'

                # mark student in the file as present
                students[student_id] = (date, True)

            line_count += 1

    # empty file check
    if len(students) < 1:
        return 'There are no students present in this file.'

    return(students)


def parse_downloaded_report(end_time: str, threshold: int, file_path="files/Test.csv") -> dict:
    """
        Parse given CSV attendance file for the MS Teams Attendance report. 
        Includes checks for headings, different timestamps, empty student list & invalid end_time.

        :param end_time: The meeting end timestamp
        :param threshold: Seconds of activity required to be marked as present
        :return students: Dictionary with student roll number (as given in the file) as key
        and tuple (date, Boolean) as value
    """

    students = {}
    date = ''
    with open(file_path, mode='r') as csv_file:

        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0

        # process the file

        for row in csv_reader:
            if line_count == 0:  # heading row

                if row != ['Full Name', 'User Action', 'Timestamp']:
                    return 'Wrong headings'

            else:

                student_id = str(int(row[0].split('.')[0]))
                action = row[1]  # 'Left' (0) or 'Joined (1)'
                timestamp = parser.parse(row[2], dayfirst=True)

                date = timestamp.date()  # extract date

                # check to see if all dates in the file are consistent
                if date != parser.parse(end_time, dayfirst=True).date():

                    return 'Different dates. Wut.'

                # first appearance of student in the file
                if student_id not in students.keys():
                    students[student_id] = {
                        'action': 1,  # first entry is always 'Join'
                        'duration': 0,  # in seconds, 0 since 'Left' has not been encountered yet
                        'time': timestamp
                    }

                # update student with the corresponding action
                else:
                    if action == 'Left':

                        # update duration for which student was in the meeting
                        a = max(timestamp, students[student_id]['time'])
                        b = min(timestamp, students[student_id]['time'])

                        # update student status to 'Left'
                        students[student_id]['action'] = 0
                        students[student_id]['duration'] += (
                            a-b).total_seconds()

                        # update 'last seen' timestamp
                        students[student_id]['time'] = timestamp

                    else:

                        # update student status to 'Joined'
                        students[student_id]['action'] = 1

                        # update 'last seen' timestamp
                        students[student_id]['time'] = timestamp

            line_count += 1

    # apply threshold barrier to extracted data
    for key, value in students.items():

        # check for invalid meeting end time
        if value['time'] > parser.parse(end_time):
            return 'Meeting end time cannot be before timestamps in the file'

        # update duration if the file did not contain 'Left' data for a student
        if value['action'] == 1:
            value['duration'] += (parser.parse(end_time, dayfirst=True) -
                                  value['time']).total_seconds()

        value['duration'] = int(value['duration'])

        # threshold logic
        if value['duration'] > threshold:
            students[key] = (date, True)
        else:
            students[key] = (date, False)

    # empty file check
    if len(students) < 1:
        return 'There are no students present in this file.'

    return(students)


def make_report(course: dict, file_path: str, type: int, format: int) -> tuple:
    """
        Create attendance report file for the given course details and file specs.
        Includes check for empty file and missing data.

        :param course: Dict containing course details
        :param file_path: The application's configured upload folder (.files) where the file
        will be stored
        :param type: Kind of the attendance report - Regular (1) or Defaulter (0)
        :param format: Format of the attendance report - XLSX (1) or CSV (0)

        :return (filename, Bool): The filename + extension of the created file, Success
    """

    course.pop('_id')

    # empty file check
    if course['students'] is None:
        return 'This course has no students enrolled?', False

    # fields in the result file will Roll Number, date1, date2....
    fields = ['Roll Number']
    dates = sorted(course['dates'])
    fields.extend(dates)
    rows = []

    for key, value in course['students'].items():

        # missing data check
        if value == {}:
            return 'This course has no/missing attendance details WYD', False

        else:

            # number of date columns
            total_days = len(dates)

            # number of present days
            days_attended = len([x for x, y in value.items() if y is True])

            # add this student to the file only if it is a regular report
            # or the attendance is less than 50% for a defaulter report

            if type == 1 or (type == 0 and (days_attended/total_days) < 0.50):

                # create row to be appended - roll, present1, present2...
                row = [key]
                for date in dates:
                    row.append(value[date])

                rows.append(row)

    # name of the result report
    filename = f'{course["course_id"]}_{course["batch"]}_asOf_{max(fields[1:])}'
    if type == 0:
        filename += '(Defaulter)'

    # complete path of the result report
    total_file_path = f'{file_path}/{filename}.csv'

    # create CSV report
    with open(total_file_path, 'w') as csvfile:
        csvwriter = csv.writer(csvfile)

        csvwriter.writerow(fields)

        csvwriter.writerows(rows)

    # create XLSX report from CSV
    if format == 1:
        csv_data = pd.read_csv(total_file_path)

        total_file_path = f'{file_path}/{filename}.xlsx'
        excel_file = pd.ExcelWriter(total_file_path)
        csv_data.to_excel(excel_file, index=False)

        excel_file.save()

    return(filename+['.csv', '.xlsx'][format == 1], True)


def remove_whitespaces(data: dict) -> dict:
    """
        Removes whitespaces from the surface level of keys & values and 1 nested level of lists
        :param data: Input dict
        :return new_data: Cleaned dict
    """

    new_data = {}
    for key, value in data.items():

        if isinstance(value, str):
            new_data[key.strip()] = value.strip()

        elif isinstance(value, list):
            new_data[key.strip()] = [x.strip() for x in value]

        else:
            new_data[key.strip()] = value

    return new_data


def attribute_check(attributes: list, form_data: dict, extras=[]) -> bool:
    """
        Check whether the elements in attributes & extras are present in the keys of 
        form_data and vice versa.
    """

    for attribute in attributes:
        if attribute not in form_data.keys():
            return f'{attribute} missing :('

    for attribute in form_data.keys():
        if attribute not in attributes+extras+['token', 'api']:
            return f'{attribute} is an invalid attribute >:O'

    return True
