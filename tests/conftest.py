import pytest
import subprocess


@pytest.fixture(scope="session", autouse=True)
def start_localstack():
    subprocess.check_output(["localstack", "start", "-d"])

    yield

    subprocess.check_output(["localstack", "stop"])
