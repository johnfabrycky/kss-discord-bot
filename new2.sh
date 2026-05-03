    # Make sure you are on the main branch
    git checkout main

    # Find the hash of the commit right BEFORE the merge
    git log --oneline

    # Reset main back to that commit. Use --hard to discard all changes.
    # Be careful with this command!
    git reset --hard 06fa811

    # Now, redo the merge correctly
    git merge --no-ff 06fa811
    