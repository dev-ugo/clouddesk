variable "storage_account_id" {
  description = "Azure resource ID of the existing CloudDesk storage account."
  type        = string
}

import {
  to = azurerm_storage_account.clouddesk
  id = var.storage_account_id
}