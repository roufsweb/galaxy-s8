param (
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Query
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$scriptDir\search_history.py" $Query

