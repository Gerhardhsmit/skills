<#
.SYNOPSIS
  Create CTTX outreach DRAFTS in Outlook Desktop under the gerhard@cttx.co.za account. Never sends.

.DESCRIPTION
  Reads every *.draft.json in -Folder (written by the CTTX outreach engine) and creates one Outlook
  draft per file in the Drafts folder of the account whose SMTP address is -Account.
  Attachments (e.g. the SIGNAL brief PDF) are added when the path exists.
  Processed files are moved to .\pushed\ so a re-run never duplicates drafts.

  Draft JSON shape:
    { "to": "name@company.co.za", "cc": "", "subject": "...", "body": "plain text",
      "attachments": ["C:\\...\\Entity_CTTX_Brief.pdf"], "prospect": "Entity", "email_status": "PUBLISHED" }

  Drafts with email_status INFERRED get "[VERIFY ADDRESS] " prefixed to the subject so they cannot be
  sent by accident without checking.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File push_outlook_drafts.ps1 -Folder "G:\My Drive\CTTX\Outreach\ready"
#>
param(
  [Parameter(Mandatory = $true)][string]$Folder,
  [string]$Account = "gerhard@cttx.co.za",
  [string]$Signature = ""   # optional: path to the approved .htm signature; empty = Outlook default signature
)

$ErrorActionPreference = "Stop"
$outlook = New-Object -ComObject Outlook.Application
$ns = $outlook.GetNamespace("MAPI")

$acct = $null
foreach ($a in $ns.Accounts) { if ($a.SmtpAddress -ieq $Account) { $acct = $a } }
if (-not $acct) {
  Write-Error "Account $Account not found in this Outlook profile. Accounts present: $(( $ns.Accounts | ForEach-Object { $_.SmtpAddress }) -join ', ')"
  exit 1
}
$drafts = $acct.DeliveryStore.GetDefaultFolder(16)   # olFolderDrafts
$pushed = Join-Path $Folder "pushed"
New-Item -ItemType Directory -Force -Path $pushed | Out-Null

$log = @()
Get-ChildItem -Path $Folder -Filter *.draft.json | ForEach-Object {
  $d = Get-Content $_.FullName -Raw | ConvertFrom-Json
  $mail = $drafts.Items.Add(0)                        # olMailItem created inside the CTTX Drafts folder
  $mail.SendUsingAccount = $acct
  $mail.To = $d.to
  if ($d.cc) { $mail.CC = $d.cc }
  $subject = $d.subject
  if ($d.email_status -eq "INFERRED") { $subject = "[VERIFY ADDRESS] " + $subject }
  $mail.Subject = $subject
  $mail.Display($false) | Out-Null                    # loads the default signature into HTMLBody
  $sig = $mail.HTMLBody
  $bodyHtml = ($d.body -replace "&", "&amp;" -replace "<", "&lt;" -replace ">", "&gt;") -replace "`r?`n", "<br>"
  if ($Signature -and (Test-Path $Signature)) { $sig = Get-Content $Signature -Raw }
  $mail.HTMLBody = "<div style='font-family:Calibri,Arial;font-size:11pt'>$bodyHtml</div>" + $sig
  foreach ($p in $d.attachments) {
    if (-not $p) { continue }
    if (-not [System.IO.Path]::IsPathRooted($p)) { $p = Join-Path $Folder $p }   # brief PDF sits beside the JSON
    if (Test-Path $p) { $mail.Attachments.Add($p) | Out-Null } else { Write-Warning "Attachment not found: $p" }
  }
  $mail.Save()
  $mail.Close(0)                                      # olSave — closes the inspector, keeps the draft
  Move-Item $_.FullName (Join-Path $pushed $_.Name) -Force
  $log += [pscustomobject]@{ Prospect = $d.prospect; To = $d.to; Subject = $subject; Saved = (Get-Date) }
}

$log | Format-Table -AutoSize
Write-Host "Drafts created in $Account -> Drafts: $($log.Count). Nothing was sent."
