terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.11.0"
    }
  }
}

provider "azurerm" {
  features {}

  use_cli                         = true
  storage_use_azuread             = true
  resource_provider_registrations = "none"
}