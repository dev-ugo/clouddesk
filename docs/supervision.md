# CloudDesk monitoring and diagnostics

Practical session on **October 19, 2026**, on `app-clouddesk-dev`, hosted in Azure App Service Linux, in France Central, with the F1 plan. The explanations are in French; Azure menu and field names are in English.

The goal is to find traffic, examine individual requests, configure the startup check, and review the record of an Azure change.

## 1. Observe requests in Metrics

Open **App Services → app-clouddesk-dev → Monitoring → Metrics**.

Check that the **Scope** is the Web App. App Service plan metrics are not available on the F1 tier; application metrics are used here.

Configure:

| Field | Value |
| --- | --- |
| First metric | `Requests` |
| Second metric, via `Add metric` | `Http 404` |
| Aggregation, for both | `Sum` |
| Time range | `Last hour` |
| Time granularity | `1 minute` |

Time settings are in the time range selector above the chart, usually at the top right. The button may display a period such as `Last 24 hours`. Open this selector, change the settings, and select **Apply**.

### Steps performed

1. Open the Azure domain with `/health` and refresh the page five times.
2. Click **Refresh** in Metrics and observe the recent data points.
3. Add the `Http 404` metric.
4. Open `/route-inexistante` and refresh this page three times.
5. Refresh the chart to find these 404 responses.

**Confirmed result:** the calls produced visible activity in `Requests`, followed by an increase in `Http 404`. No exact total of data points was recorded.

### Read the chart

`Requests` counts all requests regardless of their status. `Http 404` counts those that return 404. With `Sum` and a one-minute granularity, each point represents a total during that minute, not a per-second rate.

Data may appear with a delay. Values may also include other calls: automatic browser requests, platform checks, and requests to the SCM management site. A page refresh therefore does not necessarily correspond to a single event in the counters.

## 2. Save charts in a private dashboard

A view configured in Metrics must be saved to make it easy to find again. Azure retains metric data independently of saving this view.

With both metrics displayed:

1. Select **Save to dashboard → Pin to dashboard**.
2. Choose **Create new** and name the dashboard **CloudDesk - Dev**.
3. Choose **Private** if the panel offers this option, then confirm pinning.
4. Open **Dashboard** in the main Azure menu.
5. Select **CloudDesk - Dev** from the list next to the current dashboard's name.

If it is missing from the list, choose **Browse all dashboards** and look for the current account's private dashboards. The private dashboard is not a resource in the `rg-clouddesk-dev` group.

**Confirmed result:** the created dashboard was found again after leaving the Metrics screen.

It retains the visualization configuration; its charts query metrics for the displayed time range. Its JSON export has not yet been added to the repository. The steps above allow the view to be recreated in another account.

## 3. Read requests in Log stream

Open **Monitoring → App Service logs** in the Web App. Enable **Application logging → File System** if needed, keep the suggested quota, and select **Save**. A retention period of **1 day** was suggested for the exercise; check the value actually saved in the portal.

Open **Monitoring → Log stream**, wait for the connection, then open `/health` and `/route-inexistante` from another tab.

### Observed excerpts

Connection addresses and ports are omitted from this excerpt:

```text
2026-10-19T13:19:16.994014Z INFO: ... "GET /robots933456.txt HTTP/1.1" 404 Not Found
2026-10-19T13:19:30.2056378Z INFO: ... "GET /favicon.ico HTTP/1.1" 404 Not Found
2026-10-19T13:19:31.2271196Z INFO: ... "GET /route-inexistante HTTP/1.1" 404 Not Found
2026-10-19T13:19:33.0601879Z INFO: ... "GET /health HTTP/1.1" 200 OK
```

| Item | Interpretation |
| --- | --- |
| Timestamp ending in `Z` | UTC time; on October 19, 2026, 13:19 UTC corresponds to 15:19 in Geneva. |
| `INFO` | Level of the message logged by the server. |
| `GET` | HTTP method used. |
| `/health` | Requested path. |
| `200 OK` or `404 Not Found` | HTTP status of the response. |

### Interpret the paths

| Path | Observation and explanation |
| --- | --- |
| `/health` | 200 response: the API is responding. |
| `/route-inexistante` | Expected 404 response for a route missing from our application. |
| `/favicon.ico` | 404 response to a site icon request made by the browser. |
| `/robots933456.txt` | Default App Service warm-up path, before our customization. |

**Confirmed result:** the 200 and 404 calls were found individually in Log stream. The additional calls explain why the counters do not correspond solely to requests triggered deliberately.

## 4. Configure warm-up on /health

Warm-up is the check performed when the container starts. By default, App Service calls `/robots933456.txt` and accepts any HTTP response as a sign that the container can respond, unless configured otherwise.

For CloudDesk, the chosen approach is to use the existing `/health` route and require status 200.

Open **Settings → Environment variables → App settings**. Add:

| Name | Value |
| --- | --- |
| `WEBSITE_WARMUP_PATH` | `/health` |
| `WEBSITE_WARMUP_STATUSES` | `200` |

Select **Apply** in the add dialogs, then **Apply** on the main page. Changing app settings triggers a restart.

Return to **Monitoring → Log stream** and look for a new startup request to `/health`, with a 200 response. Also open `/health` in the browser to check the API's response.

**Result confirmed during the exercise:** the settings were applied and the startup check on `/health` was confirmed. The excerpt of the new warm-up lines was not retained in this report.

### Why this choice?

The platform now waits for a response from the route intended to check CloudDesk. This configuration concerns startup readiness; it does not configure the separate **Health check** feature, a continuous availability probe, or an alert rule.

Our `/health` route returns a static response and does not check any external dependencies. If the application later uses a database, its checking strategy will need to be reassessed.

## 5. Find the change in Activity log

Open **Activity log** in the Web App menu. Select a time range covering the change, then **Refresh**. Events can take 3 to 20 minutes to appear.

The following information was recorded during the session:

| Field | Observation |
| --- | --- |
| Operation name | `Update web sites config` |
| Time stamp | `Mon Oct 19 2026 15:23:36 GMT+0200` |
| Resource, relevant suffix | `/providers/Microsoft.Web/sites/app-clouddesk-dev/config/appsettings` |

The `config/appsettings` suffix shows that the operation targets the application's settings. The subscription ID was omitted from the documentation.

Open the event to review **Status**, **Event initiated by**, and the detailed properties in the **JSON** tab. The expected result of a successful change is **Succeeded**. This status was not copied into the information provided during the session; the report therefore does not assign it an observed value.

Activity log is collected automatically for administration operations. HTTP calls to `/health` are examined here in the application's metrics and logs.

## 6. Choose the right screen for an investigation

| Practical question | Screen used |
| --- | --- |
| How many requests are arriving, and how many return 404? | **Monitoring → Metrics** |
| How can I find my saved charts? | **Dashboard → CloudDesk - Dev** |
| Which path was called and with what HTTP status? | **Monitoring → Log stream** |
| Which startup setting needs to be configured? | **Settings → Environment variables → App settings** |
| When did an administration operation take place and which identity triggered it? | **Activity log** |

## Official references

- [App Service metrics and quotas](https://learn.microsoft.com/en-us/azure/app-service/web-sites-monitor)
- [Available metrics for Microsoft.Web/sites](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/supported-metrics/microsoft-web-sites-metrics)
- [Azure Monitor Metrics Explorer](https://learn.microsoft.com/en-us/azure/azure-monitor/metrics/analyze-metrics)
- [Azure portal dashboards](https://learn.microsoft.com/en-us/azure/azure-portal/azure-portal-dashboards)
- [App Service logs and Log stream](https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs)
- [Warm-up settings](https://learn.microsoft.com/en-us/azure/app-service/reference-app-settings)
- [App settings configuration](https://learn.microsoft.com/en-us/azure/app-service/configure-common)
- [Activity log](https://learn.microsoft.com/en-us/azure/azure-monitor/fundamentals/activity-log)

[Back to README](../README.md) · [Deployment guide](deploiement.md)
