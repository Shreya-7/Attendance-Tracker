FROM python:3
COPY ./website  /attendance
WORKDIR /attendance

# set environment variables  
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1  
# run this command to install all dependencies  
RUN pip3 install -r requirements.txt  
# port where the Django app runs  
ENV FLASK_APP=app.py
EXPOSE 5000  
ENTRYPOINT [ "flask"]
CMD [ "run", "--host", "0.0.0.0" ]