# FROM python:3.8-slim-bullseye
FROM python:3.8


ADD ./requirements.txt .requirements.txt
RUN pip3 install -r .requirements.txt


RUN pip3 install pytest

ADD . .
RUN pip install -e .




# Run the tests
CMD ["python", "-m", "unittest", "discover", "tests", "-v"]