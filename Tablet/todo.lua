-- Simple Todo List for ComputerCraft / CC:Tweaked
package.path = package.path .. ";.apis/?.lua"
require("displaymanager")
require("tableapi")
local tasks = {}
local scroll = 1
local topPane = nil
local bottomPane = nil
local input = ""


function screenSplit()
    termX, termY = term.getSize()
    topPane = window.create(term.current(),1,1,termX,termY-2)
    bottomPane = window.create(term.current(),1,termY-1,termX,termY)
end


local function loadTasks(saveFile)
    if fs.exists(saveFile) then
        local f = fs.open(saveFile, "r")
        if f then
            local data = f.readAll()
            f.close()
            local ok, t = pcall(textutils.unserialize, data)
            if ok and type(t) == "table" then tasks = t end
        end
    end
end

local function tryRemove(num)
    local t = tasks[num]
    if not t then return false end
    
    bottomPane.clear()
    bottomPane.setCursorPos(1, 1)
    out("Remove \"" .. t .. "? (y/n): ",bottomPane)
    out(">",bottomPane)
    bottomPane.setCursorPos(2,2)
    local confirm = read()
    if confirm and confirm:lower():sub(1,1) == "y" then
        table.remove(tasks, num)
        saveTasks("tasks.txt")
        return true
    end
    return false
end

function saveTasks(saveFile)
    local f = fs.open(saveFile, "w")
    if f then
        f.write(textutils.serialize(tasks))
        f.close()
    end
end

local function displayTasks()
    topPane.clear()
    bottomPane.clear()
    slicelist = slice(tasks,scroll,math.min(termY-2+scroll,#tasks))
    for i=1, #slicelist do
        out(i+(scroll-1)..": ",topPane)
        local x,y = topPane.getCursorPos()
        
        if #tasks < 10 then
        largefile = 4
        
    elseif #tasks < 100 then
        largefile = 5
    else
        largefile = 6
    end
        topPane.setCursorPos(largefile,y)
        outnl(slicelist[i],topPane)
    end
    outnl("#=rm #-#=swap exit=quit",bottomPane)
    out(">",bottomPane)
end

local function trySwap(a,b)
    if a < 1 or b < 1 or a > #tasks or b > #tasks then return false end
    tasks[a], tasks[b] = tasks[b], tasks[a]
    saveTasks("tasks.txt")
    return true
end

function todoMain()
    while true do
    loadTasks("tasks.txt")
    screenSplit()
    displayTasks()

    term.setCursorPos(2, termY)
    out(input,bottomPane)

    local event, p1 = os.pullEvent()

    if event == "char" then
        if not(#input > termX-2) then
        input = input .. p1
        end
    elseif event == "key" then
        if p1 == keys.backspace then
            input = input:sub(1, -2)
        elseif p1 == keys.enter then
            local lower = input:lower()

            if lower == "exit" then
                term.clear()
                term.setCursorPos(1,1)
                break
            end

            local a,b = input:match("^(%d+)%-(%d+)$")
            if a and b then
                a = tonumber(a); b = tonumber(b)
                trySwap(a,b)
            elseif tonumber(input) and input:match("^%d+$") then
                local num = tonumber(input)
                tryRemove(num)
            elseif #input > 0 then
                table.insert(tasks, input)
                saveTasks("tasks.txt")
            end

            input = ""
        elseif p1 == keys.up then
            scroll = math.max(1, scroll-1)
        elseif p1 == keys.down then
            scroll = math.min(math.max(#tasks - (termY - 2) + 1, scroll), scroll + 1)
        end
    end
end
end



