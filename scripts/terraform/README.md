# ease-Desk Terraform Deployment

This directory contains Infrastructure-as-Code (IaC) templates to seamlessly deploy ease-Desk to a DigitalOcean droplet.

## Prerequisites
- [Terraform](https://developer.hashicorp.com/terraform/downloads) installed locally.
- A DigitalOcean Account and a Personal Access Token.
- An SSH Key added to your DigitalOcean account (optional, but recommended).

## Quick Start

1. **Initialize Terraform:**
   ```bash
   terraform init
   ```

2. **Configure your Variables:**
   Create a `terraform.tfvars` file:
   ```hcl
   do_token    = "dop_v1_YOUR_DIGITAL_OCEAN_TOKEN"
   region      = "nyc3"
   ssh_key_ids = ["your-ssh-fingerprint"]
   ```

3. **Deploy:**
   ```bash
   terraform apply
   ```

4. **Access your Workspace:**
   Once the provisioning is complete, Terraform will output the `droplet_ip`.
   Wait ~2 minutes for the cloud-init script to install Docker and build the container, then visit:
   `http://<droplet_ip>:6080`
