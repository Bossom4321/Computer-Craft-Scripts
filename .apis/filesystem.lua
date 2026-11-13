
-- ".Documents/"
-- or "disk"
function fileList(dir)
    dir = dir or "disk"
    fileList = fs.list(dir)
    return fileList
end