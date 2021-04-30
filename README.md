This app is meant to automate the attendance tracking and maintenance process for teachers teaching via online platforms. The only thing required of the teacher is to register the courses and upload the attendance reports available via the platforms. The app takes care of the entire process of date-wise logging and tracking, as well as other filtering features. The teachers can download attendance and defaulter reports in two formats (XLSX, CSV).

## RUNNING THE APP:

1. Change the directory: **`cd website`**
2. Run via Docker (or go to step 3):
   - **Note**: This process will take up 1.03 GB of data. Also, use `sudo` with the docker commands if you are getting a permissions error.
   - Build the image: **`docker build . -t attendance_image`**
   - Run the container: **`docker run -p 5000:5000 attendance_image`**
3. Run manually:
   - Install dependencies: **`pip3 install -r requirements.txt`**
   - Set the environment variable: **`export FLASK_APP=app.py`**
   - Run the app: **`flask run`**

## FEATURES:

1. Track attendance for multiple courses and maintain it across multiple batches.
2. Set **duration** - Attendance for only those students will be counted who were present in the meeting for atleast these many seconds to weed out entries which were there only because the student logged into the meeting for a tiny amount of a time.
3. Add **flagged students**, that is, while uploading an attendance report, mark students (by their _Full Name_ as in the file) to be marked as absent even if they were present for atleast the **duration** as specified above. This makes sure you can weed out those who you feel were simply logged in but weren't responsive/attentive.
4. Download the latest attendance report showing the attendance status of every student on every tracked date, updated after every upload.
5. Download the defaulter report showing those students who were not present for atleast 50% of the classes.
6. Both these files can be downloaded in either XLSX or CSV format. The attendance reports can be uploaded in either format also.
7. Delete courses (based on their batch) for which you do not wish to keep data for anymore.

## ASSUMPTIONS:

- Only MS Teams reports having the format (Full Name, User Action, Timestamp) are accepted. Examples are provided in the _test_files_ directory.
- The _Roll Number_ field provided in the course details file is the same as the _Full Name_ field in the MS Team report. This is extremely important for the attendance tracking to happen.
  As a workaround to this, the _Roll Number_ field can be put the same as the _Name_ in the course details file.
- Only XLSX and CSV formats are accepted.
- A course is distinguished by a combination of its ID _and_ Batch. For example, a course **CS50** can have multiple entries, distinguished by its _batch_ year (like 2016, 2017 etc)
- A meeting starts and ends on the same calendar day. This means that an uploaded attendance report having multiple dates in the timestamps will provide the user with an error.
- Any and all dates associated will be in the **day, month, year** format.

## FILE INFO:

- **Dockerfile** - used to containerise this app.

**In the website directory**:

- **files** - is the standard upload directory configured in the app. It is used as temporary store for all uploaded and created files. It is refreshed every time the _index_ route is visited.
- **static** - contains all the static assets used in the app (CSS & JS files)
  - **bootstrap** - contains all the template design code
  - **css** - has an additional stylesheet _style.css_
  - **js** - has an additional script _script.js_ which is imperative to the functionality of the app, not the API
- **templates** - has all the HTML files used in the app
  - _layout.html_ - contains boilerplate HTML code and links to all the static files.
  - _home.html_ - extends _layout.html_ and is shown when the user is logged in.
  - _index.html_ - extends _layout.html_ and is shown when the user is logged out.
- **app.py** - contains all the routes needed for the app and the API. It has one extra route not used in the app (_api_signup_) but imperative for the API.
- **db_util.py** - contains utility functions pertaining to database querying.
- **decorators.py** - contains decorators created for different kinds of error handling.
- **file_util.py** - contains utility functions pertaining to file handling. It contains the core logic of this app (parsing the input files and creating reports).
- **requirements.txt** - states all the dependencies which have to be installed to run this app.

**In the test_files directory**:

- **students.csv** - example file showing how course info has to be uploaded to the app. A file of this format has to be attached when adding a course.
- **Test*.*** files - are example reports showing how attendance info has to be uploaded to the app. A file of this format in either XLSX or CSV has to be uploaded when adding attendance.
- One XLSX file showing how the downloaded attendance report looks like. The same can be downloaded in CSV format.
- One CSV file showing the downloaded defaulter report looks like. The same can be downloaded in XLSX format.

Additionally, the complete documentation for the usage of the API has been included as a PDF file. Using these instructions, the API has been independently made use of in another application called **testing** for AEPWeb.

## FUTURE SCOPE:

- Take the defaulter cutoff as input
- Add JS examples for each endpoint in the API documentation
- Tighten up security to further prevent unauthorised access
