variable "do_token" {
  description = "DigitalOcean API Token"
  type        = string
  sensitive   = true
}

variable "region" {
  description = "DigitalOcean Region"
  type        = string
  default     = "nyc3"
}

variable "droplet_size" {
  description = "Droplet Size (Minimum 1GB recommended)"
  type        = string
  default     = "s-1vcpu-1gb"
}

variable "droplet_name" {
  description = "Name for the Droplet"
  type        = string
  default     = "easedesk-workstation"
}

variable "ssh_key_ids" {
  description = "List of SSH Key IDs or fingerprints to add to the droplet"
  type        = list(string)
  default     = []
}
