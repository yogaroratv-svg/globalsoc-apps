param([Parameter(Mandatory)][string]$Subscription,
      [string]$ResourceGroup = 'rg-globalsoc-api-lab',
      [string]$Location = 'australiaeast')
$ErrorActionPreference = 'Stop'
function AzRun { param([string[]]$Arguments)
    $result = & az @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI failed: $($Arguments[0])" }
    return $result
}
if (-not $env:LAB_KEY -or -not $env:FP_SECRET) { throw 'Set LAB_KEY and FP_SECRET to random secrets first.' }
AzRun @('account','set','--subscription',$Subscription)
foreach ($provider in @('Microsoft.App','Microsoft.OperationalInsights','Microsoft.ContainerRegistry')) {
    AzRun @('provider','register','--namespace',$provider,'--wait','-o','none')
}
AzRun @('group','create','-n',$ResourceGroup,'-l',$Location,'-o','none')
AzRun @('monitor','log-analytics','workspace','create','-g',$ResourceGroup,'-n','law-api-lab','--retention-time','30','-o','none')
$lawId = AzRun @('monitor','log-analytics','workspace','show','-g',$ResourceGroup,'-n','law-api-lab','--query','customerId','-o','tsv')
$lawKey = AzRun @('monitor','log-analytics','workspace','get-shared-keys','-g',$ResourceGroup,'-n','law-api-lab','--query','primarySharedKey','-o','tsv')
AzRun @('containerapp','env','create','-g',$ResourceGroup,'-n','env-api-lab','-l',$Location,'--logs-workspace-id',$lawId,'--logs-workspace-key',$lawKey,'-o','none')
AzRun @('containerapp','up','-g',$ResourceGroup,'-n','api-lab','--environment','env-api-lab','--source','.','--ingress','external','--target-port','8000')
AzRun @('containerapp','secret','set','-g',$ResourceGroup,'-n','api-lab','--secrets',"lab-key=$env:LAB_KEY","fp-secret=$env:FP_SECRET",'-o','none')
AzRun @('containerapp','update','-g',$ResourceGroup,'-n','api-lab','--min-replicas','1','--max-replicas','1','--set-env-vars','LAB_KEY=secretref:lab-key','FP_SECRET=secretref:fp-secret','MODE=baseline','COOKIE_SECURE=true','-o','none')
AzRun @('containerapp','show','-g',$ResourceGroup,'-n','api-lab','--query','properties.configuration.ingress.fqdn','-o','tsv')
