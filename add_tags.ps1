# Get the commit history for the main branch
git log --pretty=format:'%h %s' main > commits.txt

# Loop through the commits in reverse order
$commits = Get-Content commits.txt
foreach ($line in $commits) {
    # Extract the commit hash and message
    $commit_hash = $line.Split(" ")[0]
    $commit_message = $line.Substring($commit_hash.Length + 1)

    # Check if the commit message starts with a version pattern
    if ($commit_message -match '^v[0-9]+\.[0-9]+\.[0-9]+') {
        # Extract the version number from the commit message
        $version = $commit_message.Split(" ")[0]

        # Remove the trailing colon from the version number
        $version = $version.TrimEnd(":")

        # Check if the tag already exists on the remote repository
        $tag_exists = git ls-remote --tags origin $version | Select-String -Quiet $version

        if (-not $tag_exists) {
            # Create a tag for the commit with the commit message as the tag message
            git tag -a $version -m "$commit_message" $commit_hash
            git push origin $version

            Write-Host "Created tag $version for commit $commit_hash with message: $commit_message"
        } else {
            Write-Host "Tag $version already exists on the remote repository"
        }
        # only last commit
        break;
    }
}

# Clean up the temporary file
Remove-Item commits.txt