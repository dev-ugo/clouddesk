terraform {
  backend "azurerm" {
    storage_account_name = "stclouddesktfstateugo"
    container_name       = "tfstate"
    key                  = "clouddesk-dev.tfstate"
    use_azuread_auth     = true
    use_cli              = true
  }
}
