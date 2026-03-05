<#
.SYNOPSIS
Hash artifacts for a CMMC Assessment to maintain integrity in the event any files are needed
in the future
.DESCRIPTION
This script will recursively evaluate all files in a local or UNC path. Each file will be
hashed and written to a text file. Additionally, the record is hashed to preserve the integrity
of the output
.PARAMETER ArtifactRootDirectory
Specifies the root path of the CMMC assessment artifacts. This location can be represented
by a traditional Windows file path, a UNC path, or even .\
.PARAMETER ArtifactOutputDirectory
Specifies the directory where the script will write two log files. The first log is the
listing of all files within the ArtifactRootDirectory as well as the corresponding hash. The
second log, is a hashed value of the first log. This is a simple way to help preserve the
integrity of the artifact listing without requiring the maintenance of a public/private key pair
or a password for an HMAC
#>
#VERSION 1.11
param
(
    [Parameter(mandatory=$false)][string]$ArtifactRootDirectory = ".\",
    [Parameter(mandatory=$false)][string]$ArtifactOutputDirectory = ".\"
)

function GetFileHashes ([string] $rootLocation, [boolean] $isDirectory)
{
    if ($isDirectory)
    {
        $hashList = Get-ChildItem -path $rootLocation -Recurse -Force -File | Get-FileHash
    }
    else
    {
        $hashList = Get-FileHash $rootLocation
    }
    return $hashList
}

function WriteASCIIFile ([string] $filePath, [object] $fileContent)
{
    Out-File -FilePath $filePath -Force -Encoding ASCII -InputObject $fileContent -Width 1024
}

function VerifyLocationExist ([string] $location)
{
    try
    {
        $doesExist = Test-Path $location
        if (-Not $doesExist)
        {
            ECHO "Location $location does not exist"
            throw
        }
    }
    catch
    {
        ECHO "The program failed to evaluate the path. Perhaps you specified an incorrectly formatted command line parameter?"
        EXIT
    }
}

function IsDirectory ([string] $location)
{
    $isDirectory = (get-item $location) -is [System.IO.DirectoryInfo]
    return $isDirectory
}

$version = "1.11"
ECHO "Artifact Hashing Script Version $version"

#Just making sure locations are legit
ECHO "Verifying existence of $ArtifactRootDirectory"
VerifyLocationExist $ArtifactRootDirectory

ECHO "Verifying existence of $ArtifactOutputDirectory"
VerifyLocationExist $ArtifactOutputDirectory

#determine if the input provided is for a single file or for a directory of files
$artifactLocationIsDir = IsDirectory($ArtifactRootDirectory)
$logFileLocationIsDir = IsDirectory($ArtifactOutputDirectory)

if($logFileLocationIsDir)
{
    $logFileLocation = $ArtifactOutputDirectory + "\CMMCAssessmentArtifacts.log"
    $hashedLogFileLocation = $ArtifactOutputDirectory + "\CMMCAssessmentLogHash.log"
}
else
{
    $endOfString = $ArtifactOutputDirectory.LastIndexOf("\")
    $logFileLocation = $ArtifactOutputDirectory.Substring(0,$endOfString) + "\CMMCAssessmentArtifacts.log"
    $hashedLogFileLocation = $ArtifactOutputDirectory.Substring(0,$endOfString) + "\CMMCAssessmentLogHash.log"
}

#return the list of artifacts with their hashed values
$hashedFiles = GetFileHashes $ArtifactRootDirectory $artifactLocationIsDir

ECHO "Writing artifact file listing to $logFileLocation"
WriteASCIIFile $logFileLocation $hashedFiles

#Now, I'm going to create a second file hashing the artifacts file
$hashTheHash = GetFileHashes $logFileLocation $false

ECHO "Writing hashed value of artifact file listing to $hashedLogFileLocation"
WriteASCIIFile $hashedLogFileLocation $hashTheHash

ECHO "SCRIPT COMPLETE"
