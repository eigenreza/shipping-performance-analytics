// Azure App Service on the Free (F1) Linux plan for the demo. No other resource.
// Usage: az deployment group create -g <resource group> -f deploy/main.bicep -p appName=<name>
// To use an existing Free plan instead, pass existingPlanId.

@description('Web app name (part of the public address).')
param appName string = 'shipping-performance-analytics'

@description('Region, the same as the plan.')
param location string = resourceGroup().location

@description('Resource ID of an existing Free (F1) Linux plan; leave empty to create one.')
param existingPlanId string = ''

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = if (empty(existingPlanId)) {
  name: '${appName}-plan'
  location: location
  kind: 'linux'
  sku: {
    name: 'F1'
    tier: 'Free'
  }
  properties: {
    reserved: true
  }
}

resource site 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: empty(existingPlanId) ? plan.id : existingPlanId
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appCommandLine: 'python -m uvicorn app:app --host 0.0.0.0 --port 8000'
      alwaysOn: false
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
    }
  }
}

resource settings 'Microsoft.Web/sites/config@2023-12-01' = {
  parent: site
  name: 'appsettings'
  properties: {
    SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
    WEBSITES_PORT: '8000'
  }
}

output url string = 'https://${site.properties.defaultHostName}'
