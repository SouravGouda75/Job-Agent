# ==============================================================================
# scripts/run_cycle.ps1
# Automated Job Application Cycle Runner with Safety Controls & Anti-Ban Protections
# ==============================================================================

param (
    [switch]$Supervised = $false,
    [switch]$SkipBrowser = $false
)

$ErrorActionPreference = "Continue"
$WorkspaceRoot = "C:\Users\gouda\OneDrive\Desktop\ME\CODING\JOB Agent"
Set-Location $WorkspaceRoot

# Ensure logs directory
$logDate = Get-Date -Format 'yyyy-MM-dd_HH-mm'
$logFile = "$WorkspaceRoot\logs\run_$logDate.log"
$statsFile = "$WorkspaceRoot\logs\daily_stats.json"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $formatted = "[$timestamp] [$Level] $Message"
    Write-Output $formatted
    $formatted | Out-File -FilePath $logFile -Append -Encoding utf8
}

Write-Log "================================================================="
Write-Log "🚀 STARTING JOB HUNTING APPLICATION CYCLE"
Write-Log "================================================================="

# ------------------------------------------------------------------------------
# 1. Load and parse .env settings
# ------------------------------------------------------------------------------
$envFile = "$WorkspaceRoot\.env"
$config = @{}
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $config[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
        }
    }
}

$ollamaUrl = if ($config["OLLAMA_BASE_URL"]) { $config["OLLAMA_BASE_URL"] } else { "http://localhost:11434" }
$geminiKey = $config["GEMINI_API_KEY"]
$openRouterKey = $config["OPENROUTER_API_KEY"]
$maxAppsPerCycle = if ($config["MAX_APPLICATIONS_PER_CYCLE"]) { [int]$config["MAX_APPLICATIONS_PER_CYCLE"] } else { 10 }
$dailyMaxLinkedIn = if ($config["DAILY_MAX_LINKEDIN"]) { [int]$config["DAILY_MAX_LINKEDIN"] } else { 40 }
$minDelay = if ($config["MIN_DELAY_SECONDS"]) { [int]$config["MIN_DELAY_SECONDS"] } else { 45 }
$maxDelay = if ($config["MAX_DELAY_SECONDS"]) { [int]$config["MAX_DELAY_SECONDS"] } else { 90 }

# ------------------------------------------------------------------------------
# 2. Check Daily Safety Limits (Anti-Ban Protections)
# ------------------------------------------------------------------------------
$todayStr = Get-Date -Format 'yyyy-MM-dd'
$stats = @{ date = $todayStr; linkedin_count = 0; indeed_count = 0; glassdoor_count = 0 }

if (Test-Path $statsFile) {
    try {
        $savedStats = Get-Content $statsFile -Raw | ConvertFrom-Json
        if ($savedStats.date -eq $todayStr) {
            $stats.linkedin_count = [int]$savedStats.linkedin_count
            $stats.indeed_count = [int]$savedStats.indeed_count
            $stats.glassdoor_count = [int]$savedStats.glassdoor_count
        }
    } catch {
        Write-Log "Initializing fresh daily counters." "WARN"
    }
}

Write-Log "Daily Application Counters for ${todayStr}:"
Write-Log "  LinkedIn:  $($stats.linkedin_count) / $dailyMaxLinkedIn"
Write-Log "  Indeed:    $($stats.indeed_count) / $($config['DAILY_MAX_INDEED'])"
Write-Log "  Glassdoor: $($stats.glassdoor_count) / $($config['DAILY_MAX_GLASSDOOR'])"

if ($stats.linkedin_count -ge $dailyMaxLinkedIn) {
    Write-Log "🛑 LinkedIn daily safety cap reached ($dailyMaxLinkedIn). Skipping LinkedIn applications for today to prevent ban." "WARN"
}

# ------------------------------------------------------------------------------
# 3. Verify AI Brains (Ollama & Gemini)
# ------------------------------------------------------------------------------
Write-Log "Checking AI brain status..."
$ollamaAlive = $false
try {
    $resp = curl.exe -s --max-time 5 "$ollamaUrl/api/tags"
    if ($resp -like "*models*") {
        $ollamaAlive = $true
        Write-Log "✅ Ollama Brain is active at $ollamaUrl"
    }
} catch {
    Write-Log "⚠️ Ollama endpoint unreachable. Will fallback to Gemini." "WARN"
}

# ------------------------------------------------------------------------------
# 4. ATS Scoring and Resume Tailoring Phase
# ------------------------------------------------------------------------------
Write-Log "Running ATS Resume Matcher & Tailoring..."
$tailorResult = python -u "$WorkspaceRoot\scripts\match_resume.py" --tailor 2>&1
$tailorResult | Out-File -FilePath $logFile -Append -Encoding utf8
Write-Log "✅ ATS Tailoring complete. Materials ready in tailored_resumes/"

# ------------------------------------------------------------------------------
# 5. Browser Automation Session (100% Free Stealth Agent - Zero OpenRouter)
# ------------------------------------------------------------------------------
if ($SkipBrowser) {
    Write-Log "Skipping browser application phase as requested (-SkipBrowser)."
} else {
    Write-Log "Launching Stealth Browser session (powered by Local Ollama / Gemini)..."
    $targetRole = if ($config["TARGET_ROLES"]) { $config["TARGET_ROLES"].Split(",")[0].Trim() } else { "Software Engineer" }
    $location = if ($config["TARGET_LOCATION"]) { $config["TARGET_LOCATION"] } else { "Remote" }
    $headlessArg = if ($Supervised -or $config["HEADLESS_MODE"] -eq "False") { "" } else { "--headless" }
    
    $agentScript = "$WorkspaceRoot\scripts\stealth_browser_agent.py"
    $browserOutput = python -u $agentScript --apply --role "$targetRole" --location "$location" --max 5 $headlessArg 2>&1
    $browserOutput | Out-File -FilePath $logFile -Append -Encoding utf8
    
    # Update daily stats
    $stats.linkedin_count += 5
    $stats | ConvertTo-Json | Out-File -FilePath $statsFile -Encoding utf8
    Write-Log "Session logged. Total LinkedIn applications today: $($stats.linkedin_count)"
}

Write-Log "================================================================="
Write-Log "✅ APPLICATION CYCLE COMPLETED AT $(Get-Date)"
Write-Log "================================================================="
