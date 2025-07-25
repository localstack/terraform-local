import os
import random
import subprocess
import tempfile
import uuid
import json
from typing import Dict, Generator
from shutil import rmtree
from packaging import version


import boto3
import pytest
import hcl2

# TODO set up the tests to run with tox so we can run the tests with different python versions


THIS_PATH = os.path.abspath(os.path.dirname(__file__))
ROOT_PATH = os.path.join(THIS_PATH, "..")
TFLOCAL_BIN = os.path.join(ROOT_PATH, "bin", "tflocal")
LOCALSTACK_ENDPOINT = "http://localhost:4566"


@pytest.mark.parametrize("customize_access_key", [True, False])
def test_customize_access_key_feature_flag(monkeypatch, customize_access_key: bool):
    monkeypatch.setenv("CUSTOMIZE_ACCESS_KEY", str(customize_access_key))

    # create buckets in multiple accounts
    access_key = mock_access_key()
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", access_key)
    bucket_name = short_uid()

    create_test_bucket(bucket_name)

    s3_bucket_names_default_account = get_bucket_names()
    s3_bucket_names_specific_account = get_bucket_names(aws_access_key_id=access_key)

    if customize_access_key:
        # if CUSTOMISE_ACCESS_KEY is enabled, the bucket name is only in the specific account
        assert bucket_name not in s3_bucket_names_default_account
        assert bucket_name in s3_bucket_names_specific_account
    else:
        # if CUSTOMISE_ACCESS_KEY is disabled, the bucket name is only in the default account
        assert bucket_name in s3_bucket_names_default_account
        assert bucket_name not in s3_bucket_names_specific_account


def _profile_names() -> Generator:
    yield short_uid()
    yield "default"


def _generate_test_name(param: str) -> str:
    return "random" if param != "default" else param


@pytest.mark.parametrize("profile_name", _profile_names(), ids=_generate_test_name)
def test_access_key_override_by_profile(monkeypatch, profile_name: str):
    monkeypatch.setenv("CUSTOMIZE_ACCESS_KEY", "1")
    access_key = mock_access_key()
    bucket_name = short_uid()
    credentials = """[%s]
aws_access_key_id = %s
aws_secret_access_key = test
region = eu-west-1
""" % (profile_name, access_key)
    with tempfile.TemporaryDirectory() as temp_dir:
        credentials_file = os.path.join(temp_dir, "credentials")
        with open(credentials_file, "w") as f:
            f.write(credentials)

        if profile_name != "default":
            monkeypatch.setenv("AWS_PROFILE", profile_name)
        monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", credentials_file)

        create_test_bucket(bucket_name)

        extra_param = {"aws_access_key_id": None, "aws_secret_access_key": None} if profile_name == "default" else {}
        s3_bucket_names_specific_profile = get_bucket_names(**extra_param)

        monkeypatch.delenv("AWS_PROFILE", raising=False)

        s3_bucket_names_default_account = get_bucket_names()

        assert bucket_name in s3_bucket_names_specific_profile
        assert bucket_name not in s3_bucket_names_default_account


def test_access_key_override_by_provider(monkeypatch):
    monkeypatch.setenv("CUSTOMIZE_ACCESS_KEY", "1")
    access_key = mock_access_key()
    bucket_name = short_uid()
    create_test_bucket(bucket_name, access_key)

    s3_bucket_names_default_account = get_bucket_names()
    s3_bucket_names_specific_account = get_bucket_names(aws_access_key_id=access_key)

    assert bucket_name not in s3_bucket_names_default_account
    assert bucket_name in s3_bucket_names_specific_account


def test_s3_path_addressing():
    # Temporarily change "." -> "-" as aws provider >5.55.0 fails with LocalStack
    # by calling aws-global pseudo region at S3 bucket creation instead of us-east-1
    bucket_name = f"bucket-{short_uid()}"
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
    # Temporarily change "." -> "-" as aws provider >5.55.0 fails with LocalStack
    # by calling aws-global pseudo region at S3 bucket creation instead of us-east-1
    bucket_name = f"bucket-{short_uid()}"
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


def test_s3_backend_with_multiple_backends_in_files():
    state_bucket = f"tf-state-{short_uid()}"
    bucket_name = f"bucket-{short_uid()}"
    config_main = """
    terraform {
      backend "s3" {
        bucket = "%s"
        key    = "terraform.tfstate"
        region = "us-east-2"
        skip_credentials_validation = true
      }
    }
    resource "aws_s3_bucket" "test-bucket" {
      bucket = "%s"
    }
    """ % (state_bucket, bucket_name)

    config_other_file = """
    terraform {}
    """

    # we manually need to add different files and create them to verify the fix
    with tempfile.TemporaryDirectory(delete=True) as temp_dir:
        with (
            open(os.path.join(temp_dir, "test.tf"), "w") as f,
            open(os.path.join(temp_dir, "test_2.tf"), "w") as f2,
        ):
            f.write(config_main)
            f2.write(config_other_file)

        kwargs = {"cwd": temp_dir, "env": dict(os.environ)}
        run([TFLOCAL_BIN, "init"], **kwargs)
        run([TFLOCAL_BIN, "apply", "-auto-approve"], **kwargs)

    # assert that bucket with state file exists
    s3 = client("s3", region_name="us-east-2")
    result = s3.list_objects(Bucket=state_bucket)
    keys = [obj["Key"] for obj in result["Contents"]]
    assert "terraform.tfstate" in keys


def test_s3_backend_state_lock_default():
    state_bucket = f"tf-state-{short_uid()}"
    bucket_name = f"bucket-{short_uid()}"
    state_region = "us-west-1"
    dynamodb_client = client("dynamodb", region_name=state_region)
    table_amount = len(dynamodb_client.list_tables()["TableNames"])
    config = """
    terraform {
      backend "s3" {
        bucket = "%s"
        key    = "terraform.tfstate"
        region = "%s"
        skip_credentials_validation = true
      }
    }
    resource "aws_s3_bucket" "test-bucket" {
      bucket = "%s"
    }
    """ % (state_bucket, state_region, bucket_name)
    deploy_tf_script(config)

    # assert that bucket with state file exists
    s3 = client("s3", region_name=state_region)
    result = s3.list_objects(Bucket=state_bucket)
    keys = [obj["Key"] for obj in result["Contents"]]
    assert "terraform.tfstate" in keys

    # assert that DynamoDB table with state file locks has not been created by default
    result = dynamodb_client.list_tables()
    assert len(result["TableNames"]) == table_amount

    # assert that S3 resource has been created
    s3 = client("s3")
    result = s3.head_bucket(Bucket=bucket_name)
    assert result["ResponseMetadata"]["HTTPStatusCode"] == 200


def test_s3_remote_data_source():
    state_bucket = f"tf-data-source-{short_uid()}"
    bucket_name = f"bucket-{short_uid()}"
    object_key = f"obj-{short_uid()}"
    config = """
    terraform {
      backend "s3" {
        bucket = "%s"
        key    = "terraform.tfstate"
        region = "us-east-1"
        skip_credentials_validation = true
      }
    }

    resource "aws_s3_bucket" "test_bucket" {
      bucket = "%s"
    }

    output "bucket_name" {
        value = aws_s3_bucket.test_bucket.bucket
    }
    """ % (state_bucket, bucket_name)
    deploy_tf_script(config)

    # assert that bucket with state file exists
    s3 = client("s3", region_name="us-east-2")
    result = s3.list_objects(Bucket=state_bucket)
    keys = [obj["Key"] for obj in result["Contents"]]
    assert "terraform.tfstate" in keys

    # assert that S3 resource has been created
    s3 = client("s3")
    result = s3.head_bucket(Bucket=bucket_name)
    assert result["ResponseMetadata"]["HTTPStatusCode"] == 200

    # now deploy the part that needs the S3 remote state
    config += """
    data "terraform_remote_state" "remote_data" {
      backend = "s3"

      config = {
        bucket = "%s"
        key    = "terraform.tfstate"
        region  = "us-east-1"
      }
    }

    resource "aws_s3_object" "foo" {
        bucket = data.terraform_remote_state.remote_data.outputs.bucket_name
        key    = "%s"
        content = "test"
    }

    """ % (state_bucket, object_key)
    deploy_tf_script(config)

    get_obj = s3.get_object(Bucket=bucket_name, Key=object_key)
    assert get_obj["Body"].read() == b"test"


def test_s3_remote_data_source_with_workspace(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    state_bucket = f"tf-data-source-{short_uid()}"
    config = """
    terraform {
      backend "s3" {
        bucket = "%s"
        key    = "terraform.tfstate"
        region = "us-east-1"
        skip_credentials_validation = true
      }
    }

    data "terraform_remote_state" "terraform_infra" {
      backend   = "s3"
      workspace = terraform.workspace

      config = {
        bucket               = "<state-bucket>"
        workspace_key_prefix = "terraform-infrastructure/place"
        key                  = "terraform.tfstate"
      }
    }

    data "terraform_remote_state" "build_infra" {
      backend   = "s3"
      workspace = "build"

      config = {
        bucket               = "<state-bucket>"
        workspace_key_prefix = "terraform-infrastructure"
        key                  = "terraform.tfstate"
      }
    }

    """.replace("<state-bucket>", state_bucket)

    temp_dir = deploy_tf_script(config, cleanup=False, user_input="yes")
    override_file = os.path.join(temp_dir, "localstack_providers_override.tf")
    assert check_override_file_exists(override_file)

    with open(override_file, "r") as fp:
        result = hcl2.load(fp)
        assert result["data"][0]["terraform_remote_state"]["terraform_infra"]["workspace"] == "${terraform.workspace}"
        assert result["data"][1]["terraform_remote_state"]["build_infra"]["workspace"] == "build"


@pytest.mark.parametrize("provider_version", ["5.99.1", "6.0.0-beta2"])
def test_versioned_endpoints(monkeypatch, provider_version):
    sns_topic_name = f"test-topic-{short_uid()}"
    config = """
    terraform {
      required_providers {
        aws = {
          source  = "hashicorp/aws"
          version = "= %s"
        }
      }
    }

    provider "aws" {
      region                   = "us-east-1"
      access_key               = "test"
      secret_key               = "test"
      skip_credentials_validation = true
      skip_metadata_api_check   = true
      skip_requesting_account_id = true
      endpoints {
        sns = "http://localhost:4566"
      }
    }

    resource "aws_sns_topic" "example" {
      name = "%s"
    }
    """ % (provider_version, sns_topic_name)

    with tempfile.TemporaryDirectory(delete=True) as temp_dir:
        with open(os.path.join(temp_dir, "test.tf"), "w") as f:
            f.write(config)

        # we need the `terraform init` command to create a lock file, so it cannot be a `DRY_RUN`
        run([TFLOCAL_BIN, "init"], cwd=temp_dir, env=dict(os.environ))
        monkeypatch.setenv("DRY_RUN", "1")
        run([TFLOCAL_BIN, "apply", "-auto-approve"], cwd=temp_dir, env=dict(os.environ))

        override_file = os.path.join(temp_dir, "localstack_providers_override.tf")
        assert check_override_file_exists(override_file)

        with open(override_file, "r") as fp:
            result = hcl2.load(fp)
            endpoints = result["provider"][0]["aws"]["endpoints"][0]
            if provider_version == "5.99.1":
                assert "iotanalytics" in endpoints
                assert "iotevents" in endpoints
            else:
                # we add this assertion to be sure, but Terraform wouldn't deploy with them
                assert "iotanalytics" not in endpoints
                assert "iotevents" not in endpoints


def test_dry_run(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    state_bucket = "tf-state-dry-run"
    state_table = "tf-state-dry-run"
    # Temporarily change "." -> "-" as aws provider >5.55.0 fails with LocalStack
    # by calling aws-global pseudo region at S3 bucket creation instead of us-east-1
    bucket_name = "bucket-dry-run"
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
    is_legacy_tf = is_legacy_tf_version(get_version())

    temp_dir = deploy_tf_script(config, cleanup=False, user_input="yes")
    override_file = os.path.join(temp_dir, "localstack_providers_override.tf")
    assert check_override_file_exists(override_file)

    check_override_file_backend_endpoints_content(override_file, is_legacy=is_legacy_tf)

    # assert that bucket with state file exists
    s3 = client("s3", region_name="us-east-2")

    with pytest.raises(s3.exceptions.NoSuchBucket):
        s3.list_objects(Bucket=state_bucket)

    # assert that DynamoDB table with state file locks exists
    dynamodb = client("dynamodb", region_name="us-east-2")
    with pytest.raises(dynamodb.exceptions.ResourceNotFoundException):
        dynamodb.describe_table(TableName=state_table)

    # assert that S3 resource has been created
    s3 = client("s3")
    with pytest.raises(s3.exceptions.ClientError):
        s3.head_bucket(Bucket=bucket_name)


def test_service_endpoint_alias_replacements(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    config = """
    provider "aws" {
      region = "eu-west-1"
    }"""

    temp_dir = deploy_tf_script(config, cleanup=False, user_input="yes")
    override_file = os.path.join(temp_dir, "localstack_providers_override.tf")
    assert check_override_file_content(override_file)
    rmtree(temp_dir)


def check_override_file_content(override_file):
    try:
        with open(override_file, "r") as fp:
            result = hcl2.load(fp)
            result = result["provider"][0]["aws"]
    except Exception as e:
        raise Exception(f'Unable to parse "{override_file}" as HCL file: {e}')

    endpoints = result["endpoints"][0]
    if "config" in endpoints and "configservice" in endpoints:
        return False
    return True


def test_s3_backend_configs_merge(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    state_bucket = "tf-state-conf-merge"
    state_table = "tf-state-conf-merge"
    # Temporarily change "." -> "-" as aws provider >5.55.0 fails with LocalStack
    # by calling aws-global pseudo region at S3 bucket creation instead of us-east-1
    bucket_name = "bucket-conf-merge"
    config = """
    terraform {
      backend "s3" {
        bucket = "%s"
        key    = "terraform.tfstate"
        dynamodb_table = "%s"
        region = "us-east-2"
        skip_credentials_validation = true
        encryption = true
        use_path_style = true
        acl = "bucket-owner-full-control"
        shared_config_files = ["~/.aws/config","~/other/config"]
      }
    }
    resource "aws_s3_bucket" "test-bucket" {
      bucket = "%s"
    }
    """ % (state_bucket, state_table, bucket_name)
    temp_dir = deploy_tf_script(config, cleanup=False, user_input="yes")
    override_file = os.path.join(temp_dir, "localstack_providers_override.tf")
    assert check_override_file_exists(override_file)
    assert check_override_file_backend_extra_content(override_file)
    rmtree(temp_dir)


def check_override_file_backend_extra_content(override_file):
    try:
        with open(override_file, "r") as fp:
            result = hcl2.load(fp)
            result = result["terraform"][0]["backend"][0]["s3"]
    except Exception as e:
        raise Exception(f'Unable to parse "{override_file}" as HCL file: {e}')

    return result.get("use_path_style") is True and \
        result.get("encryption") is True and \
        result.get("acl") == "bucket-owner-full-control" and \
        isinstance(result.get("shared_config_files"), list) and \
        len(result.get("shared_config_files")) == 2


@pytest.mark.parametrize("endpoints", [
    '',
    'endpoint = "http://s3-localhost.localstack.cloud:4566"',
    'endpoints = { "s3": "http://s3-localhost.localstack.cloud:4566" }',
    '''
    endpoint = "http://localhost-s3.localstack.cloud:4566"
    endpoints = { "s3": "http://s3-localhost.localstack.cloud:4566" }
    '''])
def test_s3_backend_endpoints_merge(monkeypatch, endpoints: str):
    monkeypatch.setenv("DRY_RUN", "1")
    state_bucket = "tf-state-merge"
    state_table = "tf-state-merge"
    # Temporarily change "." -> "-" as aws provider >5.55.0 fails with LocalStack
    # by calling aws-global pseudo region at S3 bucket creation instead of us-east-1
    bucket_name = "bucket-merge"
    config = """
    terraform {
      backend "s3" {
        bucket = "%s"
        key    = "terraform.tfstate"
        dynamodb_table = "%s"
        region = "us-east-2"
        skip_credentials_validation = true
        %s
      }
    }
    resource "aws_s3_bucket" "test-bucket" {
      bucket = "%s"
    }
    """ % (state_bucket, state_table, endpoints, bucket_name)
    is_legacy_tf = is_legacy_tf_version(get_version())
    if is_legacy_tf and endpoints not in ("", 'endpoint = "http://s3-localhost.localstack.cloud:4566"'):
        with pytest.raises(subprocess.CalledProcessError):
            deploy_tf_script(config, user_input="yes")
    else:
        temp_dir = deploy_tf_script(config, cleanup=False, user_input="yes")
        override_file = os.path.join(temp_dir, "localstack_providers_override.tf")
        assert check_override_file_exists(override_file)
        check_override_file_backend_endpoints_content(override_file, is_legacy=is_legacy_tf)
        rmtree(temp_dir)


def check_override_file_exists(override_file):
    return os.path.isfile(override_file)


def check_override_file_backend_endpoints_content(override_file, is_legacy: bool = False):
    legacy_options = {
        "endpoint",
        "iam_endpoint",
        "dynamodb_endpoint",
        "sts_endpoint",
    }
    new_options = {
        "iam",
        "dynamodb",
        "s3",
        "sso",
        "sts",
    }
    try:
        with open(override_file, "r") as fp:
            result = hcl2.load(fp)
            result = result["terraform"][0]["backend"][0]["s3"]
    except Exception as e:
        print(f'Unable to parse "{override_file}" as HCL file: {e}')

    if is_legacy:
        assert "endpoints" not in result
        assert legacy_options <= set(result)

    else:
        assert "endpoints" in result
        assert new_options <= set(result["endpoints"])
        assert not legacy_options & set(result)


def test_provider_aliases_ignored(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "1")
    config = """
    provider "aws" {
      region = "eu-west-1"
    }
    provider "aws" {
      alias      = "us_east_2"
      region     = "us-east-2"
      secret_key = "not-overriden"
    }
    """

    temp_dir = deploy_tf_script(config, cleanup=False, env_vars={"SKIP_ALIASES": "us_east_2"}, user_input="yes")
    override_file = os.path.join(temp_dir, "localstack_providers_override.tf")
    assert check_override_file_content_for_alias(override_file)
    rmtree(temp_dir)


def check_override_file_content_for_alias(override_file):
    try:
        with open(override_file, "r") as fp:
            result = hcl2.load(fp)
            result = result["provider"]
    except Exception as e:
        raise Exception(f'Unable to parse "{override_file}" as HCL file: {e}')

    for p in result:
        if "aws" in p and "alias" in p["aws"] and p["aws"]["alias"] == "us_east_2":
            return False
    return True


@pytest.mark.parametrize("version_flag", ["--version", "-v", "-version"])
def test_version_command(monkeypatch, version_flag):
    def _run(cmd, **kwargs):
        kwargs["stderr"] = subprocess.STDOUT
        return subprocess.check_output(cmd, **kwargs)

    with tempfile.TemporaryDirectory(delete=True) as temp_dir:
        output = _run([TFLOCAL_BIN, version_flag], cwd=temp_dir, env=dict(os.environ))
        assert b"terraform-local v" in output

        monkeypatch.setenv("DRY_RUN", "1")
        output = _run([TFLOCAL_BIN, version_flag], cwd=temp_dir, env=dict(os.environ))

        assert b"terraform-local v" in output


###
# UTIL FUNCTIONS
###


def is_legacy_tf_version(tf_version, legacy_version: str = "1.6") -> bool:
    """Check if Terraform version is legacy"""
    if tf_version < version.Version(legacy_version):
        return True
    return False


def get_version():
    """Get Terraform version"""
    output = run([TFLOCAL_BIN, "version", "-json"]).decode("utf-8")
    return version.parse(json.loads(output)["terraform_version"])


def deploy_tf_script(
    script: str,
    cleanup: bool = True,
    env_vars: Dict[str, str] = None,
    user_input: str = None,
):
    # TODO the delete keyword was added in python 3.12, and the README and setup.cfg claims compatibility
    #  with earlier python versions
    with tempfile.TemporaryDirectory(delete=cleanup) as temp_dir:
        with open(os.path.join(temp_dir, "test.tf"), "w") as f:
            f.write(script)
        kwargs = {"cwd": temp_dir}
        if user_input:
            kwargs.update({"input": bytes(user_input, "utf-8")})
        kwargs["env"] = {**os.environ, **(env_vars or {})}
        run([TFLOCAL_BIN, "init"], **kwargs)
        run([TFLOCAL_BIN, "apply", "-auto-approve"], **kwargs)
        return temp_dir


def get_bucket_names(**kwargs: dict) -> list:
    s3 = client("s3", region_name="eu-west-1", **kwargs)
    s3_buckets = s3.list_buckets().get("Buckets")
    return [s["Name"] for s in s3_buckets]


def create_test_bucket(bucket_name: str, access_key: str = None) -> None:
    access_key_section = f'access_key = "{access_key}"' if access_key else ""
    config = """
    provider "aws" {
      %s
      region = "eu-west-1"
    }
    resource "aws_s3_bucket" "test_bucket" {
      bucket = "%s"
    }""" % (access_key_section, bucket_name)
    deploy_tf_script(config)


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
