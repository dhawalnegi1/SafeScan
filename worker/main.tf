terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 3.0"
    }
  }
}
provider "cloudflare" {
  email   = "" # Replace with your Cloudflare account email
  api_key = "" # Replace with your Cloudflare API key
  account_id = "" # Replace with your Cloudflare Account ID

}
resource "cloudflare_worker_script" "proxy_worker" {
  name = "aws-proxy-worker"
  content = file("./worker.js")
}
resource "cloudflare_worker_route" "route" {
  zone_id = "" # Replace with your Cloudflare Zone ID
  pattern = ""       # Replace with your domain, e.g., example.com/*
  script_name = cloudflare_worker_script.proxy_worker.name
}
