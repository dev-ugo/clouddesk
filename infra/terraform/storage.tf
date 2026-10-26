resource "azurerm_storage_account" "clouddesk" {
  access_tier                       = "Hot"
  account_kind                      = "StorageV2"
  account_replication_type          = "LRS"
  account_tier                      = "Standard"
  allow_nested_items_to_be_public   = false
  cross_tenant_replication_enabled  = false
  default_to_oauth_authentication   = true
  dns_endpoint_type                 = "Standard"
  https_traffic_only_enabled        = true
  infrastructure_encryption_enabled = false
  is_hns_enabled                    = false
  large_file_share_enabled          = false
  local_user_enabled                = true
  location                          = "francecentral"
  min_tls_version                   = "TLS1_2"
  name                              = "stclouddeskdevugo"
  nfsv3_enabled                     = false
  public_network_access             = "Enabled"
  queue_encryption_key_type         = "Service"
  resource_group_name               = "rg-clouddesk-dev"
  sftp_enabled                      = false
  shared_access_key_enabled         = false
  table_encryption_key_type         = "Service"
  tags = {
    environment = "dev"
    owner       = "dev-ugo"
    project     = "clouddesk"
  }
  blob_properties {
    change_feed_enabled      = false
    last_access_time_enabled = false
    versioning_enabled       = true
    container_delete_retention_policy {
      days = 7
    }
    delete_retention_policy {
      days                     = 7
      permanent_delete_enabled = false
    }
  }
  share_properties {
    retention_policy {
      days = 7
    }
  }
}
