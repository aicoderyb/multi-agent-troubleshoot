$BaseUrl = if ($env:MULAT_BASE_URL) { $env:MULAT_BASE_URL } else { "http://localhost:8000" }
$body = @{
    message = "Smoke test from invoke_ask.ps1"
    source  = "powershell"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "$BaseUrl/ask" -ContentType "application/json" -Body $body
