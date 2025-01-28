FROM python:3.14.0a3-slim-bookworm

ARG TERRAFORM_VERSION=1.10.3

RUN apt-get update && \
apt-get install -yy curl unzip

# Install Terraform
RUN mkdir -p /opt/terraform
RUN set -eux \
&& OS=$(uname -s | tr '[:upper:]' '[:lower:]') \
&& ARCH=$(uname -m | sed -e 's/x86_64/amd64/' -e 's/aarch64/arm64/') \
&& TERRAFORM_URL="https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_${OS}_${ARCH}.zip" \
&& curl -o /tmp/terraform.zip "${TERRAFORM_URL}" \
&& unzip /tmp/terraform.zip -d /opt/terraform \
&& rm /tmp/terraform.zip \
&& chmod +x /opt/terraform/terraform

ENV PATH="/opt/terraform:${PATH}"

# Install terraform-local
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:/opt/terraform:$PATH"
RUN pip install --no-cache-dir terraform-local
