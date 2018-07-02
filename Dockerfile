FROM kennethreitz/pipenv:latest

COPY . .

CMD ["python3", "run.py"]