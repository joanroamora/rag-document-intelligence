terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }

  backend "gcs" {
    bucket = "bitcitychamp-project-tfstate"
    prefix = "env/dev"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
