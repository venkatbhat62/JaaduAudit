### powershell command




#Get installed certificates from localmachine 
$certs = Get-ChildItem Cert:\ -Recurse| Format-Table -AutoSize
#Display results in console
$certs |format-list |Out-String
# FriendlyName, NotAfter,NotBefore

exit
$result=@()
$ErrorActionPreference="SilentlyContinue"
$getcert=Get-ChildItem -Path Cert:\LocalMachine\ -Recurse 
foreach ($cert in $getcert) {
$result+=New-Object -TypeName PSObject -Property ([ordered]@{
'Certificate'=$cert.Issuer;
'Expires'=$cert.NotAfter
})
}
Write-Output $result
