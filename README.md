[![Build status](https://github.com/localstack/terraform-local/actions/workflows/build.yml/badge.svg)](https://github.com/localstack/terraform-local/actions)

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
* `DRY_RUN`: Generate the override file without invoking Terraform
* `TF_CMD`: Terraform command to call (default: `terraform`)
* `AWS_ENDPOINT_URL`: hostname and port of the target LocalStack instance
* `LOCALSTACK_HOSTNAME`: __(Deprecated)__ host name of the target LocalStack instance
* `EDGE_PORT`: __(Deprecated)__ port number of the target LocalStack instance
* `S3_HOSTNAME`: special hostname to be used to connect to LocalStack S3 (default: `s3.localhost.localstack.cloud`)
* `USE_EXEC`: whether to use `os.exec` instead of `subprocess.Popen` (try using this in case of I/O issues)
* `<SERVICE>_ENDPOINT`: setting a custom service endpoint, e.g., `COGNITO_IDP_ENDPOINT=http://example.com`
* `AWS_DEFAULT_REGION`: the AWS region to use (default: `us-east-1`, or determined from local credentials if `boto3` is installed)
* `CUSTOMIZE_ACCESS_KEY`: enables to override the static AWS Access Key ID. The following cases are taking precedence over each other from top to bottom:
    * `AWS_ACCESS_KEY_ID` environment variable is set
    * `access_key` is set in the Terraform AWS provider
    * `AWS_PROFILE` environment variable is set and configured
    * `AWS_DEFAULT_PROFILE` environment variable is set and configured
    * `default` profile's credentials are configured
    * falls back to the default `AWS_ACCESS_KEY_ID` mock value
* `AWS_ACCESS_KEY_ID`: AWS Access Key ID to use for multi account setups (default: `test` -> account ID: `000000000000`)
* `SKIP_ALIASES`: Allows to skip generating AWS provider overrides for specified aliased providers, e.g. `SKIP_ALIASES=aws_secrets,real_aws`
* `ADDITIONAL_TF_OVERRIDE_LOCATIONS`: Comma-separated list of folder paths that will also receive a temporary `localstack_providers_override.tf` file

## Usage

The `tflocal` command has the same usage as the `terraform` command. For detailed usage,
please refer to the man pages of `terraform --help`.

### Validation errors when using local terraform modules

Note that if your project uses local terraform modules, and those modules reference providers, those folders *also* need to receive a temporary `localstack_providers_override.tf` file. Without it, you would get an error that looks like this when starting to process code from inside the module

```
╷
│ Error: No valid credential sources found
│ 
│   with module.lambda.provider["registry.terraform.io/hashicorp/aws"],
│   on ../../providers.tf line 11, in provider "aws":
│   11: provider "aws" {
│ 
│ Please see https://registry.terraform.io/providers/hashicorp/aws
│ for more information about providing credentials.
│ 
│ Error: failed to refresh cached credentials, no EC2 IMDS role found, operation error ec2imds: GetMetadata, access disabled to EC2 IMDS via client option, or "AWS_EC2_METADATA_DISABLED" environment variable
```

To address this issue, you may include a comma-separated list of folder paths that will recieve additional override files via an environment variable

```
ADDITIONAL_TF_OVERRIDE_LOCATIONS=/path/to/module1,path/to/module2 tflocal plan
```

[See this issue for more discussion](https://github.com/localstack/terraform-local/issues/67)

## Change Log

* v0.24.1: Exclude broken `python-hcl2` version from requirements
* v0.24.0: Add support to return `terraform-local` version when calling `tflocal -version` and fix AWS provider detection
* v0.23.1: Fix endpoint overrides for Terraform AWS provider >= 6.0.0-beta2
* v0.23.0: Add support for `terraform_remote_state` with `s3` backend to read the state stored in local S3 backend; fix S3 backend config detection with multiple Terraform blocks
* v0.22.0: Fix S3 backend forcing DynamoDB State Lock to be enabled by default
* v0.21.0: Add ability to drop an override file in additional locations
* v0.20.1: Fix list config rendering
* v0.20.0: Fix S3 backend option merging
* v0.19.0: Add `SKIP_ALIASES` configuration environment variable
* v0.18.2: Fix warning on aliased custom endpoint names
* v0.18.1: Fix issue with not proxied commands
* v0.18.0: Add `DRY_RUN` and patch S3 backend entrypoints
* v0.17.1: Add `packaging` module to install requirements
* v0.17.0: Add option to use new endpoints S3 backend options
* v0.16.1: Update Setuptools to exclude tests during packaging
* v0.16.0: Introducing semantic versioning and AWS_ENDPOINT_URL variable
* v0.15: Update endpoint overrides for Terraform AWS provider 5.22.0
* v0.14: Add support to multi-account environments
* v0.13: Fix S3 automatic `use_s3_path_style` detection when setting S3_HOSTNAME or LOCALSTACK_HOSTNAME
* v0.12: Fix local endpoint overrides for Terraform AWS provider 5.9.0; fix parsing of alias and region defined as value lists
* v0.11: Minor fix to handle boolean values in S3 backend configs
* v0.10: Add support for storing state files in local S3 backends
* v0.9: Fix unsupported provider override for emrserverless
* v0.8: Configure the endpoint for opensearch service
* v0.7: Add initial support for provider aliases
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
