# `tflocal` - Terraform with LocalStack

This package provides `tflocal` - a small wrapper script to run [Terraform](https://terraform.io) against [LocalStack](https://localstack.cloud).

## Prerequisites

* Python 3.x
* `pip`
* `terraform`

## How it works

The script uses the [Terraform Override mechanism](https://www.terraform.io/language/files/override) and creates a temporary file `localstack_providers_override.tf` to configure the endpoints for the AWS `provider` section. The endpoints for all services are configured to point to the LocalStack API (`http://localhost:4566` by default).

## Installation

The `tflocal` command line interface can be installed via `pip`:
```
pip install terraform-local
```

## Configurations

The following environment variables can be configured:
* `TF_CMD`: Terraform command to call (default: `terraform`)
* `LOCALSTACK_HOSTNAME`: host name of the target LocalStack instance
* `EDGE_PORT`: port number of the target LocalStack instance
* `S3_HOSTNAME`: special hostname to be used to connect to LocalStack S3 (default: `s3.localhost.localstack.cloud`)
* `USE_EXEC`: whether to use `os.exec` instead of `subprocess.Popen` (try using this in case of I/O issues)
* `<SERVICE>_ENDPOINT`: setting a custom service endpoint, e.g., `COGNITO_IDP_ENDPOINT=http://example.com`
* `AWS_DEFAULT_REGION`: the AWS region to use (default: `us-east-1`, or determined from local credentials if `boto3` is installed)

## Usage

The `tflocal` command has the same usage as the `terraform` command. For detailed usage,
please refer to the man pages of `terraform --help`.

## Change Log

* v0.6: Fix selection of default region
* v0.5: Make AWS region configurable, add `region` to provider config
* v0.4: Fix using use_s3_path_style for S3_HOSTNAME=localhost; exclude `meteringmarketplace` service endpoint
* v0.3: Fix support for -chdir=... to create providers file in target directory
* v0.2: Add ability to specify custom endpoints; pass INT signals to subprocess
* v0.1: Initial release

## License

This software library is released under the Apache License, Version 2.0 (see `LICENSE`).

[pypi-version]: https://img.shields.io/pypi/v/terraform-local.svg
[pypi]: https://pypi.org/project/terraform-local/
