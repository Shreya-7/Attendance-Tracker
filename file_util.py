import csv
import openpyxl
import pandas as pd
import codecs

from dateutil import parser
from db_util import Database

# Heading checks have to be modified in 2 places - heading_check() and get_file_type()


class UploadedFile:

    """
        Hold generic uploaded files info and functions
    """

    def __init__(self, file_path, file_name, db_obj):
        self.file_path = file_path
        self.file_name = file_name
        self.db_obj = db_obj

        self.student_headings = ['Roll Number', 'Name']
        self.gform_headings = ['Timestamp', 'Your Roll Number']
        self.teams_headings = ['Full Name', 'User Action', 'Timestamp']

    def heading_check(self, required_headings: list, file_headings: list, strictness=1):
        """
            Check whether the `file_headings` match with the `required_headings`.
            :param `required_headings`: list of strings
            :param `file_headings`: list of strings
            :param `strictness`: Default 1 means function will check for an exact match.
            If value passed is 0, means function will check if `required_headings` is a 
            subset of `file_headings`

            :return True if matches, an error string if not
        """
        message = 'Wrong headings. Please check the Help section under the `Upload Reports tab`.'
        file_headings = [element.strip() for element in file_headings]
        if strictness == 1 and file_headings != required_headings:
            return message

        elif strictness == 0:
            for heading in required_headings:
                if heading not in file_headings:
                    return message

        return True

    def check_extension(self):
        """
            Check whether the extension of the file is either CSV or XLSX and not something else.
            :return True if extension is CSV/XLSX, an error string if not
        """
        filename, extension = self.file_name.split('.')

        if extension not in ['csv', 'xlsx']:
            return "Please upload a CSV or XLSX file only _/\_"

        return True

    def convert_to_csv(self, result_path="files/Test.csv"):
        """
            Convert given CSV/XLSX file at `file_path` to a CSV file and save in the 
            files folder.
        """

        excel = openpyxl.load_workbook(self.file_path)
        sheet = excel.active
        col = csv.writer(open(result_path, 'w', newline=""))

        for r in sheet.rows:
            col.writerow([cell.value for cell in r])

    def two_way_heading_check(self, required_headings: list, form_headings: list, extras=[]) -> bool:
        """
            Check whether the elements in attributes & extras are present in the keys of 
            form_data and vice versa.
            ! Not being used
        """

        for attribute in required_headings:
            if attribute not in form_headings:
                return f'{attribute} missing :('

        for attribute in form_headings:
            if attribute not in required_headings+extras+['token', 'api']:
                return f'{attribute} is an invalid attribute >:O'

        return True

    def get_file_type(self) -> int:
        """
            Determines the type of by its headings.
            Returns 0 for Google Form, 1 for Teams, -1 for neither
        """

        try:
            # This section works for a Google Form file or a comma separated MS Teams file
            with open(self.file_path, mode='r', encoding='utf8') as csv_file:

                csv_reader = csv.reader(csv_file, delimiter=',')
                for row in csv_reader:

                    row = [element.strip() for element in row]

                    # Gform has to be checked like this because the strictness should be 0
                    gform_check = True
                    for heading in self.gform_headings:
                        if heading not in row:
                            gform_check = False
                            break

                    if gform_check:
                        return 0
                    elif row == self.teams_headings:
                        return 1

                    else:
                        return -1
        except:
            # Try fails - assumed to be tab separated MS Teams file
            print("In except section of get_file_type()")
            uploaded_file = codecs.open(self.file_path, 'rU', 'UTF-16')
            df = pd.read_csv(uploaded_file, sep='\t')

            heads = df.columns.values.tolist()

            # This weird as hell check because for some weird as hell reason the entire weird as hell
            # heading row is being picked up as one element
            for supposed_heading in self.teams_headings:
                if supposed_heading not in heads:
                    return -1

            return 1

    def get_file_contents(self) -> list:
        """
            Saves the file contents as a list of lists, each new line becoming a new list within the parent list.
        """

        self.content = []
        try:
            # This section works for a Google Form file or a comma separated MS Teams file
            with open(self.file_path, mode='r') as csv_file:

                csv_reader = csv.reader(csv_file, delimiter=',')
                for row in csv_reader:
                    self.content.append(row)

        except:
            # Try fails - assumed to be tab separated MS Teams file
            print("In except section of get_file_contents()")
            uploaded_file = codecs.open(self.file_path, 'rU', 'UTF-16')
            df = pd.read_csv(uploaded_file, sep='\t')

            self.content = [['Full Name', 'User Action', 'Timestamp']]
            file_content = df.reset_index().values.tolist()
            for row in file_content:
                row = row[1:]
                row = [str(element) for element in row]
                self.content.append(row)


class StudentFile(UploadedFile):

    def __init__(self, file_path, file_name, db_obj):
        super().__init__(file_path, file_name, db_obj)

    def get_students_from_file(self) -> list:
        """
            Extract student details from the given filepath. 
            Includes checks for correct headings.
            :return: List of tuples of (student roll, student name)
        """
        students = []
        with open(self.file_path, mode='r', encoding='utf-8') as csv_file:

            csv_reader = csv.reader(csv_file, delimiter=',')
            line_count = 0

            for row in csv_reader:

                if line_count == 0:  # the heading row

                    head = row

                    check_result = self.heading_check(
                        self.student_headings, head, strictness=0)
                    if check_result is not True:
                        return check_result

                    # track index so that Name, Roll and Roll, Name both formats are accepted
                    roll_index, name_index = head.index(
                        'Roll Number'), head.index('Name')

                else:

                    roll, name = row[roll_index], row[name_index]
                    students.append((roll, name))

                line_count += 1

        students.sort(key=lambda x: x[0])
        return students


class GoogleFormFile(UploadedFile):

    def __init__(self, file_path, file_name, db_obj):
        super().__init__(file_path, file_name, db_obj)

    def get_date(self):
        """
            Extract dates from the file and 1) check if all are same 2) set the date member
            3) return the date
            :return (`date`, True) if everything is OK, (an error string, False) if not
        """
        dates = []
        self.get_file_contents()
        line_count = 0
        for row in self.content:

            if line_count == 0:
                timestamp_index = row.index('Timestamp')

            else:
                timestamp = parser.parse(
                    row[timestamp_index])

                extracted_date = timestamp.date()  # extract date
                dates.append(extracted_date)

            line_count += 1

        if line_count < 2:
            return 'There are no details in this file.', False

        if len(set(dates)) != 1:
            return 'There are different dates in this file! Please upload a file with only one date.', False

        else:
            self.date = str(dates[0])
            return self.date, True

    def parse_google_form_result(self, file_path="files/Test.csv") -> dict:
        """
            Parse given CSV attendance file for the Google Forms report. 
            Includes checks for headings, different timestamps & empty student list.

            :return `students`: Dictionary with student roll number (as given in the file) as key
            and tuple (date, Boolean) as value
        """
        students = {}
        self.get_file_contents()
        line_count = 0

        # process the file
        for row in self.content:

            if line_count == 0:  # heading row

                check_result = self.heading_check(
                    self.gform_headings, row, strictness=0)
                if check_result is not True:
                    return check_result

                # find indexes so that column exchange is permitted
                roll_index = row.index('Your Roll Number')
                timestamp_index = row.index('Timestamp')

            else:

                student_id = str(int(row[roll_index].split('.')[0]))
                timestamp = parser.parse(
                    row[timestamp_index])

                extracted_date = timestamp.date()  # extract date

                # mark student in the file as present
                students[student_id] = (self.date, True)

            line_count += 1

        # empty file check
        if len(students) < 1:
            return 'There are no students present in this file.'

        return(students)


class TeamsFile(UploadedFile):

    def __init__(self, file_path, file_name, db_obj):
        super().__init__(file_path, file_name, db_obj)

    def get_date(self):
        """
            Extract dates from the file and 1) check if all are same 2) set the date member
            3) return the date
            :return (`date`, True) if everything is OK, (an error string, False) if not
        """

        dates = []
        self.get_file_contents()
        line_count = 0

        # process the file
        for row in self.content:

            if line_count == 0:  # heading row
                line_count += 1
                continue
            else:
                timestamp = parser.parse(row[2], dayfirst=True)

                date = timestamp.date()  # extract date
                dates.append(date)

            line_count += 1

        if line_count < 2:
            return 'There are no details in this file.', False

        if len(set(dates)) != 1:
            return 'There are different dates in this file! Please upload a file with only one date.', False

        else:
            self.date = str(dates[0])
            return self.date, True

    def parse_downloaded_report(self, end_time: str, threshold: int, file_path="files/Test.csv") -> dict:
        """
            Parse given CSV attendance file for the MS Teams Attendance report. 
            Includes checks for headings, different timestamps, empty student list & invalid end_time.

            :param `end_time`: The meeting end timestamp
            :param `threshold`: Minutes of activity required to be marked as present
            :return `students`: Dictionary with student roll number (as given in the file) as key
            and tuple (date, Boolean) as value
        """

        students = {}
        date = ''
        self.get_file_contents()
        line_count = 0

        # process the file
        for row in self.content:
            if line_count == 0:  # heading row

                check_result = self.heading_check(
                    self.teams_headings, row)
                if check_result is not True:
                    return check_result

            else:

                student_id = str(int(row[0].split('.')[0]))
                action = row[1]  # 'Left' (0) or 'Joined (1)'
                timestamp = parser.parse(row[2], dayfirst=True)

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
            if value['duration']/60 > threshold:
                students[key] = (self.date, True)
            else:
                students[key] = (self.date, False)

        # empty file check
        if len(students) < 1:
            return 'There are no students present in this file.'

        return(students)


class Report():

    def __init__(self, folder_path: str, db_obj: Database, type: int, format: int):
        """
            :param `folder_path`: The application's configured upload folder (.files) where the file
            will be stored
            :param `db_obj`: A `Database` object to query DB
            :param `type`: Kind of the attendance report - Regular (1) or Defaulter (0)
            :param `format`: Format of the attendance report - XLSX (1) or CSV (0)
        """

        self.folder_path = folder_path
        self.db_obj = db_obj
        self.type = type
        self.format = format

    def create_csv_report(self, fields: list, rows: list):
        """
            Write the given items into a CSV file at `self.csv_file_path`.
            :param `fields`: Headings for the file
            :param `rows`: List of lists, each containing information for one row
        """
        with open(self.csv_file_path, 'w') as csvfile:
            csvwriter = csv.writer(csvfile)

            csvwriter.writerow(fields)

            csvwriter.writerows(rows)

    def create_excel_report(self):
        """
            Creates an excel report out of the CSV report already created at `self.csv_file_path`.
        """
        csv_data = pd.read_csv(self.csv_file_path)

        self.excel_file_path = f'{self.folder_path}/{self.filename}.xlsx'
        excel_file = pd.ExcelWriter(self.excel_file_path)
        csv_data.to_excel(excel_file, index=False)
        excel_file.save()

    def create_filename(self, fields):
        """
            Create the filename for the report based on the course details & latest date.
            :param `fields`: Headings for file - the dates start from the 4th item
        """

        self.filename = f'{self.db_obj.course_id}_{self.db_obj.batch}_asOf_{max(fields[3:])}'
        if self.type == 0:
            self.filename += '(Defaulter)'

    def make_report(self) -> tuple:
        """
            Create attendance report file for the given course details and file specs.
            Includes check for empty file and missing data.

            :return `(filename, Bool)`: The filename + extension of the created file, Success
        """

        course = self.db_obj.get_course()

        # empty file check
        if course['students'] is None:
            return 'This course has no students enrolled :(', False

        # fields in the result file will Sl. No., Roll Number, Name, date1, date2....
        fields = ['Sl. No.', 'Roll Number', 'Name']
        dates = sorted(course['dates'])
        fields.extend(dates)
        rows = []
        sl = 1

        for key, value in course['students'].items():

            # missing data check
            if value == {}:
                return 'This course has no/missing attendance details. Please track a date to download a report', False

            else:

                # number of date columns
                total_days = len(dates)

                # number of present days
                days_attended = len([x for x, y in value.items() if y is True])

                # add this student to the file only if it is a regular report
                # or the attendance is less than 50% for a defaulter report

                if self.type == 1 or (self.type == 0 and (days_attended/total_days) < 0.75):

                    # create row to be appended - sl no, roll, name, present1, present2...
                    row = [sl, key, self.db_obj.get_name(key)['name']]
                    for date in dates:
                        status = ['Present', 'Absent'][value[date] == False]
                        row.append(status)

                    rows.append(row)
                    sl += 1

        self.create_filename(fields)

        self.csv_file_path = f'{self.folder_path}/{self.filename}.csv'

        self.create_csv_report(fields, rows)

        if self.format == 1:
            self.create_excel_report()

        return(self.filename+['.csv', '.xlsx'][self.format == 1], True)


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
