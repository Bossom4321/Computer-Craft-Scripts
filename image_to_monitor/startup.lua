-- Required Custom APIs
package.path = package.path .. ";.apis/?.lua"
require("displaymanager")
require("utils")
require("paintutilsplus")
require("tableapi") -- Required for slice() function used in the scrolling pane

-- Globals & Peripherals
local saveFile = "boot_wpft_save.txt"
local mon = peripheral.wrap("monitor_0")
local monb = peripheral.wrap("right")
local scroll = 1
local input = ""
local topPane = nil
local bottomPane = nil
local termX, termY

-- Setup monitor scale
if mon then
    mon.setTextScale(0.5)
end

----------------------------------------
-- 1. Window Initialization
----------------------------------------
function screenSplit()
    termX, termY = term.getSize()
    topPane = window.create(term.current(), 1, 1, termX, termY - 2)
    bottomPane = window.create(term.current(), 1, termY - 1, termX, termY)
end

----------------------------------------
-- 2. Persistence Functions
----------------------------------------
local function saveImageSelection(filename)
    local f = fs.open(saveFile, "w")
    if f then
        f.write(filename)
        f.close()
    end
end

local function loadImageSelection()
    if fs.exists(saveFile) then
        local f = fs.open(saveFile, "r")
        if f then
            local data = f.readAll()
            f.close()
            return data
        end
    end
    return nil
end

----------------------------------------
-- 3. Core Drawing Logic
----------------------------------------
local function drawToMonitor(filename)
    local filepath = "disk/" .. filename
    if not mon then 
        -- Optional: output error to bottomPane if monitor is missing
        return 
    end
    rclear(mon)
    printImageDitherHex(filepath, mon)
end

----------------------------------------
-- 4. File Discovery
----------------------------------------
local function getWpftFiles()
    local wpftFiles = {}
    if not fs.exists("disk") then return wpftFiles end
    
    local files = fs.list("disk/")
    for _, file in ipairs(files) do
        if file:sub(-5) == ".wpft" then
            table.insert(wpftFiles, file)
        end
    end
    return wpftFiles
end

----------------------------------------
-- 5. Boot Logic
----------------------------------------
local savedImage = loadImageSelection()
-- Fixed missing "disk/" prefix in validation so it successfully loads on startup
if savedImage and fs.exists("disk/" .. savedImage) then
    drawToMonitor(savedImage)
end

----------------------------------------
-- 6. User Interface Loop
----------------------------------------
local function displayMenu(files)
    topPane.clear()
    bottomPane.clear()
    
    -- Print Header
    topPane.setCursorPos(1, 1)
    outnl("=== WPFT Image Selector ===", topPane)
    
    if #files == 0 then
        topPane.setCursorPos(1, 3)
        outnl("No .wpft files found in 'disk/'.", topPane)
    else
        -- Using slice to paginate the files array based on the current scroll
        -- termY - 4 ensures we account for the header and the bottom pane height
        local slicelist = slice(files, scroll, math.min((termY - 4) + scroll, #files))
        
        local yOffset = 2
        for i = 1, #slicelist do
            local fileIndex = i + (scroll - 1)
            topPane.setCursorPos(1, yOffset)
            out(fileIndex .. ": ", topPane)
            
            local x, y = topPane.getCursorPos()
            local padding = 4
            if #files >= 10 and #files < 100 then padding = 5 
            elseif #files >= 100 then padding = 6 end
            
            topPane.setCursorPos(padding, y)
            outnl(slicelist[i], topPane)
            yOffset = yOffset + 1
        end
    end
    
    outnl("Enter # to draw, 'q' or 'exit' to quit", bottomPane)
    out(">", bottomPane)
end

local function menuLoop()
    while true do
        screenSplit()
        local files = getWpftFiles()
        
        -- Update secondary right monitor with dimensions if it exists
        if monb then
            rclear(monb)
            outnl("Height by Width", monb)
            if mon then
                out(sizeX(mon), monb)
                out(" x ", monb)
                outnl(sizeY(mon), monb)
            end
        end
        
        displayMenu(files)
        
        -- Handle Input Cursor
        bottomPane.setCursorPos(2, 2)
        out(input, bottomPane)
        
        local event, p1 = os.pullEvent()
        
        if event == "char" then
            if not (#input > termX - 2) then
                input = input .. p1
            end
        elseif event == "key" then
            if p1 == keys.backspace then
                input = input:sub(1, -2)
            elseif p1 == keys.enter then
                local lower = input:lower()
                
                if lower == "q" or lower == "exit" then
                    term.clear()
                    term.setCursorPos(1, 1)
                    break
                end
                
                local choice = tonumber(input)
                if choice and choice >= 1 and choice <= #files then
                    local selected = files[choice]
                    saveImageSelection(selected)
                    drawToMonitor(selected)
                end
                
                input = ""
            elseif p1 == keys.up then
                scroll = math.max(1, scroll - 1)
            elseif p1 == keys.down then
                -- Restrict scrolling past the end of the file list
                local maxScroll = math.max(1, #files - (termY - 4) + 1)
                scroll = math.min(maxScroll, scroll + 1)
            end
        end
    end
end

-- Start the menu
menuLoop()