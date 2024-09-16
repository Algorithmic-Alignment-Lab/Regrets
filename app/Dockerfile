# Use an official Python runtime as a parent image
FROM python:3.12
RUN apt-get update && apt-get install -y ca-certificates && update-ca-certificates
# Set the working directory in the container
WORKDIR /usr/src/app

ENV PYTHONPATH="/usr/src/app:${PYTHONPATH}"
# Copy the current directory contents into the container at /usr/src/app
COPY .. .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --use-pep517 -r requirements.txt

# Define environment variable
ENV FLASK_APP=app.py