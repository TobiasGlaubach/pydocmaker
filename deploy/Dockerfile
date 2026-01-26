FROM python:3.12-slim-bullseye


ADD ./requirements.txt .requirements.txt
RUN pip3 install -r .requirements.txt


RUN pip3 install pytest

ADD . .
RUN pip install -e .




# Run the tests
CMD ["pytest", "tests"]
