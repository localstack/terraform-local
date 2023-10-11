import os
import random
import subprocess
import tempfile
import uuid
from typing import Dict

import boto3

THIS_PATH = os.path.abspath(os.path.dirname(__file__))
ROOT_PATH = os.path.join(THIS_PATH, "..")
TFLOCAL_BIN = os.path.join(ROOT_PATH, "bin", "tflocal")
LOCALSTACK_ENDPOINT = "http://localhost:4566"


def test_access_key_override_fallback(monkeypatch):
    access_key = mock_access_key()
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", access_key)
    bucket_name = short_uid()
    config = """
    provider "aws" {
      region = "eu-west-1"
    }
    resource "aws_s3_bucket" "test_bucket" {
      bucket = "%s"
    }""" % (bucket_name)
    deploy_tf_script(config)

    s3 = client("s3", region_name="eu-west-1")
    s3_buckets = s3.list_buckets().get("Buckets")
    s3_bucket_names = [s["Name"] for s in s3_buckets]

    assert bucket_name in s3_bucket_names

    s3 = client("s3", region_name="eu-west-1", aws_access_key_id=access_key)
    s3_buckets = s3.list_buckets().get("Buckets")
    s3_bucket_names = [s["Name"] for s in s3_buckets]

    assert bucket_name not in s3_bucket_names


def test_access_key_override_by_env_var(monkeypatch):
    monkeypatch.setenv("CUSTOMIZE_ACCESS_KEY", "1")
    access_key = mock_access_key()
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", access_key)
    bucket_name = short_uid()
    config = """
    provider "aws" {
      region = "eu-west-1"
    }
    resource "aws_s3_bucket" "test_bucket" {
      bucket = "%s"
    }""" % (bucket_name)
    deploy_tf_script(config)

    s3 = client("s3", region_name="eu-west-1")
    s3_buckets = s3.list_buckets().get("Buckets")
    s3_bucket_names = [s["Name"] for s in s3_buckets]

    assert bucket_name not in s3_bucket_names

    s3 = client("s3", region_name="eu-west-1", aws_access_key_id=access_key)
    s3_buckets = s3.list_buckets().get("Buckets")
    s3_bucket_names = [s["Name"] for s in s3_buckets]

    assert bucket_name in s3_bucket_names


def test_access_key_override_by_profile(monkeypatch):
    profile_name = short_uid()
    monkeypatch.setenv("CUSTOMIZE_ACCESS_KEY", "1")
    monkeypatch.setenv("AWS_PROFILE", profile_name)
    access_key = mock_access_key()
    bucket_name = short_uid()
    credentials = """
    [%s]
    aws_access_key_id = %s
    aws_secret_access_key = test
    region = eu-west-1
    """ % (profile_name, access_key)
    with tempfile.TemporaryDirectory() as temp_dir:
        credentials_file = os.path.join(temp_dir, "credentials")
        with open(credentials_file, "w") as f:
            f.write(credentials)

        monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", credentials_file)

        config = """
        provider "aws" {
          region = "eu-west-1"
        }
        resource "aws_s3_bucket" "test_bucket" {
          bucket = "%s"
        }""" % (bucket_name)
        deploy_tf_script(config)

        s3 = client("s3", region_name="eu-west-1")
        s3_buckets = s3.list_buckets().get("Buckets")
        s3_bucket_names = [s["Name"] for s in s3_buckets]

        assert bucket_name in s3_bucket_names

        monkeypatch.delenv("AWS_PROFILE")
        s3 = client("s3", region_name="eu-west-1")
        s3_buckets = s3.list_buckets().get("Buckets")
        s3_bucket_names = [s["Name"] for s in s3_buckets]

        assert bucket_name not in s3_bucket_names


def test_access_key_override_by_default_profile(monkeypatch):
    monkeypatch.setenv("CUSTOMIZE_ACCESS_KEY", "1")
    access_key = mock_access_key()
    bucket_name = short_uid()
    credentials = """
    [default]
    aws_access_key_id = %s
    aws_secret_access_key = test
    region = eu-west-1
    """ % (access_key)
    with tempfile.TemporaryDirectory() as temp_dir:
        credentials_file = os.path.join(temp_dir, "credentials")
        with open(credentials_file, "w") as f:
            f.write(credentials)

        monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", credentials_file)

        config = """
        provider "aws" {
          region = "eu-west-1"
        }
        resource "aws_s3_bucket" "test_bucket" {
          bucket = "%s"
        }""" % (bucket_name)
        deploy_tf_script(config)

        s3 = client("s3", region_name="eu-west-1")
        s3_buckets = s3.list_buckets().get("Buckets")
        s3_bucket_names = [s["Name"] for s in s3_buckets]

        assert bucket_name not in s3_bucket_names

        s3 = client("s3", region_name="eu-west-1", aws_access_key_id=None, aws_secret_access_key=None)
        s3_buckets = s3.list_buckets().get("Buckets")
        s3_bucket_names = [s["Name"] for s in s3_buckets]

        assert bucket_name in s3_bucket_names


def test_access_key_override_by_provider(monkeypatch):
    monkeypatch.setenv("CUSTOMIZE_ACCESS_KEY", "1")
    access_key = mock_access_key()
    bucket_name = short_uid()
    config = """
    provider "aws" {
      access_key = "%s"
      region = "eu-west-1"
    }
    resource "aws_s3_bucket" "test_bucket" {
      bucket = "%s"
    }""" % (access_key, bucket_name)
    deploy_tf_script(config)

    s3 = client("s3", region_name="eu-west-1")
    s3_buckets = s3.list_buckets().get("Buckets")
    s3_bucket_names = [s["Name"] for s in s3_buckets]

    assert bucket_name not in s3_bucket_names

    s3 = client("s3", region_name="eu-west-1", aws_access_key_id=access_key)
    s3_buckets = s3.list_buckets().get("Buckets")
    s3_bucket_names = [s["Name"] for s in s3_buckets]

    assert bucket_name in s3_bucket_names


def test_s3_path_addressing():
    bucket_name = f"bucket.{short_uid()}"
    config = """
    resource "aws_s3_bucket" "test-bucket" {
      bucket = "%s"
    }
    """ % bucket_name
    deploy_tf_script(config, env_vars={"S3_HOSTNAME": "localhost"})

    s3 = client("s3")
    buckets = [b["Name"] for b in s3.list_buckets()["Buckets"]]
    assert bucket_name in buckets


def test_use_s3_path_style(monkeypatch):
    monkeypatch.setenv("S3_HOSTNAME", "s3.localhost.localstack.cloud")
    import_cli_code()
    assert not use_s3_path_style()  # noqa

    monkeypatch.setenv("S3_HOSTNAME", "localhost")
    import_cli_code()
    assert use_s3_path_style()  # noqa

    # test the case where the S3_HOSTNAME could be a Docker container name
    monkeypatch.setenv("S3_HOSTNAME", "localstack")
    import_cli_code()
    assert use_s3_path_style()  # noqa

    # test the case where the S3_HOSTNAME could be an arbitrary host starting with `s3.`
    monkeypatch.setenv("S3_HOSTNAME", "s3.internal.host")
    import_cli_code()
    assert not use_s3_path_style()  # noqa


def test_provider_aliases():
    queue_name1 = f"q{short_uid()}"
    queue_name2 = f"q{short_uid()}"
    config = """
    provider "aws" {
      region = "eu-west-1"
    }
    provider "aws" {
      alias  = "us_east_2"
      region = "us-east-2"
    }
    resource "aws_sqs_queue" "queue1" {
      name = "%s"
    }
    resource "aws_sqs_queue" "queue2" {
      name = "%s"
      provider = aws.us_east_2
    }
    """ % (queue_name1, queue_name2)
    deploy_tf_script(config)

    sqs1 = client("sqs", region_name="eu-west-1")
    sqs2 = client("sqs", region_name="us-east-2")
    queues1 = [q for q in sqs1.list_queues().get("QueueUrls", [])]
    queues2 = [q for q in sqs2.list_queues().get("QueueUrls", [])]
    assert any(queue_name1 in queue_url for queue_url in queues1)
    assert any(queue_name2 in queue_url for queue_url in queues2)


def test_s3_backend():
    state_bucket = f"tf-state-{short_uid()}"
    state_table = f"tf-state-{short_uid()}"
    bucket_name = f"bucket.{short_uid()}"
    config = """
    terraform {
      backend "s3" {
        bucket = "%s"
        key    = "terraform.tfstate"
        dynamodb_table = "%s"
        region = "us-east-2"
        skip_credentials_validation = true
      }
    }
    resource "aws_s3_bucket" "test-bucket" {
      bucket = "%s"
    }
    """ % (state_bucket, state_table, bucket_name)
    deploy_tf_script(config)

    # assert that bucket with state file exists
    s3 = client("s3", region_name="us-east-2")
    result = s3.list_objects(Bucket=state_bucket)
    keys = [obj["Key"] for obj in result["Contents"]]
    assert "terraform.tfstate" in keys

    # assert that DynamoDB table with state file locks exists
    dynamodb = client("dynamodb", region_name="us-east-2")
    result = dynamodb.describe_table(TableName=state_table)
    attrs = result["Table"]["AttributeDefinitions"]
    assert attrs == [{"AttributeName": "LockID", "AttributeType": "S"}]

    # assert that S3 resource has been created
    s3 = client("s3")
    result = s3.head_bucket(Bucket=bucket_name)
    assert result["ResponseMetadata"]["HTTPStatusCode"] == 200


###
# UTIL FUNCTIONS
###

def deploy_tf_script(script: str, env_vars: Dict[str, str] = None):
    with tempfile.TemporaryDirectory() as temp_dir:
        with open(os.path.join(temp_dir, "test.tf"), "w") as f:
            f.write(script)
        kwargs = {"cwd": temp_dir}
        kwargs["env"] = {**os.environ, **(env_vars or {})}
        run([TFLOCAL_BIN, "init"], **kwargs)
        out = run([TFLOCAL_BIN, "apply", "-auto-approve"], **kwargs)
        return out


def short_uid() -> str:
    return str(uuid.uuid4())[0:8]


def mock_access_key() -> str:
    return str(random.randrange(999999999999)).zfill(12)


def client(service: str, **kwargs):
    # if aws access key is not set AND no profile is in the environment,
    # we want to set the accesss key and the secret key to test
    if "aws_access_key_id" not in kwargs and "AWS_PROFILE" not in os.environ:
        kwargs["aws_access_key_id"] = "test"
    if "aws_access_key_id" in kwargs and "aws_secret_access_key" not in kwargs:
        kwargs["aws_secret_access_key"] = "test"
    boto3.setup_default_session()
    return boto3.client(
        service,
        endpoint_url=LOCALSTACK_ENDPOINT,
        **kwargs,
    )


def run(cmd, **kwargs) -> str:
    kwargs["stderr"] = subprocess.PIPE
    return subprocess.check_output(cmd, **kwargs)


def import_cli_code():
    # bit of a hack, to import the functions from the tflocal script
    with open(TFLOCAL_BIN, "r") as f:
        exec(f.read(), globals())
