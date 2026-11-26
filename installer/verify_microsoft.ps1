param([Parameter(Mandatory=$true)][string]$Path)
$ErrorActionPreference = 'Stop'
$signature = Get-AuthenticodeSignature -FilePath $Path
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(^|,\s*)O=Microsoft Corporation(,|$)') {
    throw "Firma de Microsoft no válida: $Path ($($signature.Status))"
}
[ordered]@{
    publisher = $signature.SignerCertificate.Subject
    version = (Get-Item -LiteralPath $Path).VersionInfo.FileVersion
    sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
} | ConvertTo-Json -Compress
