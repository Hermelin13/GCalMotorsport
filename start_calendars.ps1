param(
    [switch]$F1,
    [switch]$FE,
    [switch]$WEC
)

# Support long-form args (--F1) passed from batch by normalizing $args
$allArgs = @($args)
function has-arg($name) {
    return $allArgs -contains $name -or $allArgs -contains $name.ToLower()
}


# start_calendars.ps1 — accept single --which parameter and forward extras
# Usage examples:
#   powershell -File .\start_calendars.ps1 --which all --dry-run
#   .\start_calendars.bat --which f1 --upload --calendar-id ID

# Default credentials and calendar IDs (edit as needed)
# Replace these with your real calendar IDs. If left as placeholders,
# the script will attempt upload and likely fail with API error.
$F1_CAL = 'family16658134994112439829@group.calendar.google.com'
$FE_CAL = 'family16658134994112439829@group.calendar.google.com'
$WEC_CAL = 'family16658134994112439829@group.calendar.google.com'
$CREDS = 'calendarcred.json'

# Collect raw args and find --which value (support --which=val as well)
$raw = @($args)
$whichVal = $null
$forward = @()
for ($i = 0; $i -lt $raw.Count; $i++) {
    $a = $raw[$i]
    if ($a -like '--which=*') {
        $whichVal = $a.Split('=')[1]
        continue
    }
    if ($a -ieq '--which' -or $a -ieq '-which') {
        if ($i + 1 -lt $raw.Count) {
            $whichVal = $raw[$i+1]
            $i++
            continue
        } else { continue }
    }
    $forward += $a
}

if (-not $whichVal) {
    Write-Host "No --which provided; defaulting to 'all' and running interactive fallback."
    $whichVal = 'all'
}

# Normalize which into selection array
$whichVal = $whichVal.Trim().ToLower()
if ($whichVal -eq 'all') {
    $selection = @('f1','fe','wec')
} else {
    $parts = $whichVal -split '[,;]'
    $selection = @()
    foreach ($p in $parts) {
        $v = $p.Trim()
        if ($v -in @('f1','fe','wec')) { $selection += $v }
    }
    if ($selection.Count -eq 0) { Write-Host "No valid selection in --which; defaulting to all"; $selection = @('f1','fe','wec') }
}

Write-Host "Will run: $($selection -join ', ')"

# Build forward-args string
$forwardArgs = $forward -join ' '

foreach ($s in $selection) {
    # Build base args ensuring upload and creds/calendar-id defaults are present
    $argsList = @()
    $argsList += '--which'; $argsList += $s

    # If user didn't pass --upload or --dry-run, default to upload
    $hasUpload = $forward -match '--upload'
    $hasDry = $forward -match '--dry-run'
    if (-not $hasUpload -and -not $hasDry) {
        $argsList += '--upload'
    }

    # Forward other user args except which (we already set it)
    foreach ($fa in $forward) { $argsList += $fa }

    # If no --calendar-id in forwarded args, add the mapped one
    $hasCalId = $false
    for ($i=0; $i -lt $argsList.Count; $i++) {
        if ($argsList[$i] -ieq '--calendar-id') { $hasCalId = $true; break }
        if ($argsList[$i] -like '--calendar-id=*') { $hasCalId = $true; break }
    }
    if (-not $hasCalId) {
        switch ($s) {
            'f1' { $argsList += '--calendar-id'; $argsList += $F1_CAL }
            'fe' { $argsList += '--calendar-id'; $argsList += $FE_CAL }
            'wec' { $argsList += '--calendar-id'; $argsList += $WEC_CAL }
        }
    }

    # If no --creds supplied, add default creds
    $hasCreds = $false
    for ($i=0; $i -lt $argsList.Count; $i++) {
        if ($argsList[$i] -ieq '--creds') { $hasCreds = $true; break }
        if ($argsList[$i] -like '--creds=*') { $hasCreds = $true; break }
    }
    if (-not $hasCreds) { $argsList += '--creds'; $argsList += $CREDS }

    # Build command string
    $cmd = 'python run_calendars.py ' + ($argsList -join ' ')
    Write-Host "Running: $cmd"
    iex $cmd
}

Write-Host "All done."
