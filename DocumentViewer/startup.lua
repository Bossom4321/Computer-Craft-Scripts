-- Document Viewer for ComputerCraft / CC:Tweaked
package.path = package.path .. ";.apis/?.lua"
local printerapi = require("printerapi")

local docFolder = "disk/"
local files = {}         
local menuItems = {}     
local rawDocLines = {}   -- For printing
local docLines = {}      -- For display (word-wrapped)

local state = "menu"     
local currentDocName = ""
local scroll = 0
local inputBuffer = ""   -- Holds text as the user types

local termWidth, termHeight = term.getSize()
local lastWidth = termWidth
local visibleLines = termHeight - 2

-- Ensure the directory exists


-- 1. Parse and Sort Files
local function loadAndSortFiles()
    files = fs.list(docFolder)
    
    table.sort(files, function(a, b)
        local numA = tonumber(a:match("^(%d+)=")) or 999
        local numB = tonumber(b:match("^(%d+)=")) or 999
        return numA < numB
    end)

    menuItems = {}
    for i = 1, #files do
        local raw = files[i]
        local clean = raw:match("^%d+=(.+)$") or raw
        clean = clean:gsub("%.[^%.]+$", "")
        clean = clean:gsub("_", " ")
        table.insert(menuItems, clean)
    end
end

-- 2. Word-Wrap Engine
local function formatDocument()
    docLines = {}
    for _, line in ipairs(rawDocLines) do
        if line:match("^%s*$") then
            table.insert(docLines, "")
        else
            local currentLine = ""
            for word in line:gmatch("%S+") do
                if currentLine == "" then
                    currentLine = word
                elseif #currentLine + 1 + #word <= termWidth then
                    currentLine = currentLine .. " " .. word
                else
                    table.insert(docLines, currentLine)
                    currentLine = word
                end
            end
            if currentLine ~= "" then
                table.insert(docLines, currentLine)
            end
        end
    end
end

-- 3. Load Document File
local function loadDocument(filename)
    rawDocLines = {}
    local path = fs.combine(docFolder, filename)
    if fs.exists(path) and not fs.isDir(path) then
        local f = fs.open(path, "r")
        if f then
            local line = f.readLine()
            while line do
                table.insert(rawDocLines, line)
                line = f.readLine()
            end
            f.close()
            formatDocument()
            return true
        end
    end
    return false
end

-- 4. Screen Renderer (Renders the live input buffer)
local function drawDisplay()
    term.clear()
    term.setCursorPos(1, 1)
    if fs.exists(docFolder) then
    loadAndSortFiles()
    end

    local maxItems = (state == "menu") and #menuItems or #docLines
    
    -- Clamp calculation
    local maxScroll = math.max(0, maxItems - visibleLines)
    if scroll < 0 then scroll = 0 end
    if scroll > maxScroll then scroll = maxScroll end

    -- Render visible lines
    for i = 1, visibleLines do
        local idx = scroll + i
        term.setCursorPos(1, i)
        term.clearLine()
        if idx <= maxItems and idx >= 1 then
            if state == "menu" then
                term.write(idx .. ": " .. menuItems[idx])
            else
                term.write(docLines[idx])
            end
        end
    end

    -- Help Line
    term.setTextColor(colors.lightGray)
    term.setCursorPos(1, termHeight - 1)
    term.clearLine()
    if state == "menu" then
        term.write("Enter index # to open")
    else
        term.write("back=Menu | print=Print")
    end
    term.setTextColor(colors.white)

    -- Command Prompt Line showing live buffer typing
    term.setCursorPos(1, termHeight)
    term.clearLine()
    term.write("> " .. inputBuffer)
end

-- Initial execution
loadAndSortFiles()

-- Main Event Loop
while true do
    termWidth, termHeight = term.getSize()
    visibleLines = math.max(1, termHeight - 2)
    
    if termWidth ~= lastWidth then
        lastWidth = termWidth
        if state == "view" then
            formatDocument()
        end
    end
    
    drawDisplay()

    -- Capture system events dynamically (No blocking read!)
    local event, p1 = os.pullEvent()
    
    if event == "key" then
        local maxItems = (state == "menu") and #menuItems or #docLines
        
        if p1 == keys.up then
            scroll = math.max(0, scroll - 1)
            
        elseif p1 == keys.down then
            scroll = math.min(math.max(0, maxItems - visibleLines), scroll + 1)
            
        elseif p1 == keys.backspace then
            inputBuffer = inputBuffer:sub(1, -2)
            
        elseif p1 == keys.enter then
            -- Process command execution upon hitting enter
            local command = inputBuffer:gsub("^%s+", ""):gsub("%s+$", "")
            inputBuffer = "" -- Clear the buffer for next time
            local lower = command:lower()

            if lower == "adminexit" then
                term.clear()
                term.setCursorPos(1, 1)
                break
            end

            if state == "menu" then
                local num = tonumber(command)
                if num and files[num] then
                    if loadDocument(files[num]) then
                        currentDocName = menuItems[num]
                        state = "view"
                        scroll = 0
                    end
                end
            elseif state == "view" then
                if lower == "back" or lower == "menu" then
                    state = "menu"
                    scroll = 0
                elseif lower == "print" then
                        term.clear()
                        term.setCursorPos(1, 1)
                        term.setTextColor(colors.yellow)
                        print("Sending '" .. currentDocName .. "' to printer...")
                        term.setTextColor(colors.white)
                        
                        -- Using standard "\n" ensures exact line formatting matches CC standards
                        local fullContent = table.concat(rawDocLines, "\n")
                        printPage(fullContent, currentDocName)
                        
                        sleep(1)
                    end
            end
        end
        
    elseif event == "char" then
        -- Append text characters to our visible buffer line
        inputBuffer = inputBuffer .. p1
    end
end