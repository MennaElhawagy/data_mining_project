param(
    [string]$PythonBin = "python",
    [string]$PgHost = "localhost",
    [int]$PgPort = 5432,
    [string]$PgDatabase = "instacart_dwh",
    [string]$PgUser = "postgres",
    [string]$PaperLogDir = ".\logs\paper_results",
    [int]$Workers = 0
)

$ErrorActionPreference = "Stop"

if (-not $env:PGPASSWORD) {
    $securePassword = Read-Host -Prompt "PostgreSQL password for $PgUser" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    try {
        $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$commonArgs = @(
    "--host", $PgHost,
    "--port", "$PgPort",
    "--database", $PgDatabase,
    "--user", $PgUser,
    "--log-dir", $PaperLogDir
)

if ($Workers -gt 0) {
    $commonArgs += @("--workers", "$Workers")
}

function Invoke-MiningRun {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$RunArgs
    )

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "Running: $($RunArgs -join ' ')"
    Write-Host "============================================================"
    & $PythonBin .\mining_algo\run_mining.py @commonArgs @RunArgs
}

Write-Host "Starting Instacart product-level mining research experiments"
Write-Host "Database: $PgDatabase on ${PgHost}:$PgPort"
Write-Host "Logs: $PaperLogDir"
New-Item -ItemType Directory -Force -Path $PaperLogDir | Out-Null

# Product level: Eclat and FP-Growth paper runs.
Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --refresh-baskets --notes "paper_results; product; eclat; top_100; support_0.01; confidence_0.30"
Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --notes "paper_results; product; eclat; top_100; support_0.005; confidence_0.30"
Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --notes "paper_results; product; eclat; top_100; support_0.003; confidence_0.30"

Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_100; support_0.01; confidence_0.30"
Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_100; support_0.005; confidence_0.30"
Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 100  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_100; support_0.003; confidence_0.30"

Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; eclat; top_500; support_0.01; confidence_0.30"
Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; eclat; top_500; support_0.005; confidence_0.30"
Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; eclat; top_500; support_0.003; confidence_0.30"

Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_500; support_0.01; confidence_0.30"
Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_500; support_0.005; confidence_0.30"
Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 500  --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_500; support_0.003; confidence_0.30"

Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_1000; support_0.01; confidence_0.30"
Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_1000; support_0.005; confidence_0.30"
Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_1000; support_0.003; confidence_0.30"

Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_1000; support_0.01; confidence_0.30"
Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_1000; support_0.005; confidence_0.30"
Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 1000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_1000; support_0.003; confidence_0.30"

Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_5000; support_0.01; confidence_0.30"
Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_5000; support_0.005; confidence_0.30"
Invoke-MiningRun --algorithm eclat --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; eclat; top_5000; support_0.003; confidence_0.30"

Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.01  --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_5000; support_0.01; confidence_0.30"
Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.005 --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_5000; support_0.005; confidence_0.30"
Invoke-MiningRun --algorithm fp_growth --granularity product --min-support 0.003 --min-confidence 0.30 --top-items 5000 --max-itemset-size 2 --notes "paper_results; product; fp_growth; top_5000; support_0.003; confidence_0.30"

Write-Host ""
Write-Host "All research experiments completed."
