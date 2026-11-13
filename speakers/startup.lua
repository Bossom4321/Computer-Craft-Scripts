--this code is glued together, god help you if you need to edit it
package.path = package.path .. ";.apis/?.lua"
require("displaymanager")
require("tableapi")
require("utils")
dfpwm = require("cc.audio.dfpwm")
decoder = dfpwm.make_decoder()
speaker = peripheral.find("speaker")

local scroll = 1
local topPane = nil
local bottomPane = nil
local input = ""
queue = {}
temp = 0
-- Split a string into words separated by whitespace
function split_words(s)
    local words = {}
    for w in string.gmatch(s, "%S+") do
        words[#words + 1] = w
    end
    return words
end

--splits screen so that the instructions and typing is in the bottom pane
function screenSplit()
    termX, termY = term.getSize()
    topPane = window.create(term.current(), 1, 1, termX, termY - 2)
    bottomPane = window.create(term.current(), 1, termY - 1, termX, termY)
end

--prints out the list of all the music that it found on the pc
local function displayMusic(textshown)
    topPane.clear()
    bottomPane.clear()
    slicelist = slice(musiclist, scroll, math.min(termY - 2 + scroll, #musiclist))
    for i = 1, #slicelist do
        out(i + (scroll - 1) .. ": ", topPane)
        local x, y = topPane.getCursorPos()

        if #musiclist < 10 then
            largefile = 4
        elseif #musiclist < 100 then
            largefile = 5
        else
            largefile = 6
        end
        topPane.setCursorPos(largefile, y)
        outnl(slicelist[i], topPane)
    end
    outnl(textshown, bottomPane)
    out(">", bottomPane)
end

-- Recursively search for *.dfpwn files and return names without extension
local function findDFPWNFiles(path, results)
    path = path or ""
    results = results or {}

    for _, item in ipairs(fs.list(path)) do
        local fullPath = fs.combine(path, item)

        if fs.isDir(fullPath) then
            -- Recurse into subdirectories
            findDFPWNFiles(fullPath, results)
        else
            -- Check if file ends with .dfpwn
            if item:sub(-6) == ".dfpwm" then
                -- Strip the extension and store the base name
                table.insert(results, item:sub(1, -7))
            end
        end
    end

    return results
end

function fileExists(fileName)
    return (fs.exists(fileName .. ".dfpwm"))
end

skipTrack = false

function musicFileSearch(fileName, volume)
    volume = volume or 3
    skipTrack = false

    if fileExists(fileName) then
        for chunk in io.lines(fileName .. ".dfpwm", 16 * 1024) do
            local buffer = decoder(chunk)

            while true do
                local ok = speaker.playAudio(buffer, volume)
                if ok then break end

                local event, key = os.pullEvent()

                if event == "key" and key == keys.backspace then
                    -- Start timing how long backspace is held
                    local holdStart = os.clock()

                    -- Wait for release or timeout
                    while true do
                        local e, k = os.pullEvent()

                        -- Released → skip track
                        if e == "key_up" and k == keys.backspace then
                            skipTrack = true
                            speaker.stop()
                            sleep(0.1)
                            break
                        end

                        -- Held for 0.5 seconds → exit playback
                        if os.clock() - holdStart >= 0.5 then
                            speaker.stop()
                            return "exit"
                        end
                    end

                    break
                end
            end

            if skipTrack then
                return "skipped"
            end
        end

        return true
    else
        return false
    end
end

local function displayqueue(musiclist, per, bool, volume, shuffle, loop)
    shuffle = shuffle or false
    loop = loop or false
    rclear(per)

    if per ~= term then
        per.setTextScale(0.5)
    end

    -- Shuffle helper (uses math.random(x) exactly as you want)
    local function shuffleTable(t)
        for i = #t, 2, -1 do
            local j = math.random(i) -- random number between 1 and i
            t[i], t[j] = t[j], t[i]
        end
    end

    -- PREVIEW MODE (bool == false)
    if not bool then
        outnl("", per)

        if #queue == 0 then
            outnl("Queue is empty.", per)
            return
        end

        outnl("First: " .. musiclist[queue[1]], per)
        outnl("", per)
        outnl("Next:", per)

        for i = 2, #queue do
            outnl(musiclist[queue[i]], per)
        end

        return
    end

    -- PLAYBACK MODE
    if #queue == 0 then
        outnl("Queue is empty.", per)
        sleep(1)
        return
    end

    -- Initial shuffle
    if shuffle then
        shuffleTable(queue)
    end

    local running = true

    while running do
        for i = 1, #queue do
            rclear(per)

            outnl("", per)
            outnl("Now: " .. musiclist[queue[i]], per)
            outnl("", per)
            outnl("Next:", per)

            for y = i + 1, #queue do
                outnl(musiclist[queue[y]], per)
            end

            -- Play the track (backspace = skip)
            local res = musicFileSearch(musiclist[queue[i]], volume)
            if res == "exit" then
                running = false
                break
            elseif res == "skipped" then
                -- continue to next track
            end


            -- Between tracks: allow stopping with 'p'
            local timer = os.startTimer(0.05)
            local waiting = true

            while waiting do
                local event, key = os.pullEvent()

                if event == "timer" and key == timer then
                    waiting = false
                elseif event == "key" and key == keys.p then
                    running = false
                    waiting = false
                end
            end

            if not running then break end
        end

        -- END OF QUEUE → RESHUFFLE HERE
        if shuffle and loop then
            shuffleTable(queue) -- <‑‑ THIS is the fix you asked for
        end

        if not loop then
            running = false
        end
    end

    rclear(per)
    queue = {}
end





function Main()
    while true do
        -- load music to musiclist
        musiclist = sortByLetter(findDFPWNFiles("/"))
        screenSplit()

        displayMusic("enter '?help' for guide")
        volume = 3


        term.setCursorPos(2, termY)
        out(input, bottomPane)
        if peripheral.find("monitor") then
            displayqueue(musiclist, peripheral.find("monitor"), false, volume)
        end

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

                if lower == "exit" then
                    term.clear()
                    term.setCursorPos(1, 1)
                    break


                    --playAudio
                elseif lower == "?help" then
                    rclear(term)
                    outnl("Music Player Instructions:")
                    outnl("")
                    outnl("Enter a song name or its number to add it")
                    outnl("to the queue. When you're done adding songs,")
                    outnl("type 'play' to begin playback.")
                    outnl("")
                    outnl("Backspace: tap to skip the current song")
                    outnl("Backspace (hold): exit playback and return")
                    outnl("to song selection")
                    outnl("")
                    outnl("Extra playback modes:")
                    outnl("  play loop         - repeats the queue")
                    outnl("  play shuffle      - plays songs in random order")
                    outnl("  play shuffle loop - reshuffles every loop")
                    outnl("")
                    outnl("'exit' will end the program")
                    outnl("")
                    outnl("Press Enter to return...")
                    read()
                elseif lower == "play" then
                    displayqueue(musiclist, peripheral.find("monitor") or term, true, volume)
                elseif lower == "play loop" then
                    displayqueue(musiclist, peripheral.find("monitor") or term, true, volume, false, true)
                elseif lower == "play shuffle" then
                    displayqueue(musiclist, peripheral.find("monitor") or term, true, volume, true)
                elseif lower == "play shuffle loop" or lower == "play loop shuffle" then
                    displayqueue(musiclist, peripheral.find("monitor") or term, true, volume, true, true)
                elseif tonumber(input) and inRange(tonumber(input), 0, #musiclist) then
                    table.insert(queue, tonumber(input))
                elseif fileExists(input) then
                    table.insert(queue, findindex(musiclist, input))
                end

                input = ""
            elseif p1 == keys.up then
                scroll = math.max(1, scroll - 1)
            elseif p1 == keys.down then
                scroll = math.min(math.max(#musiclist - (termY - 2) + 1, scroll), scroll + 1)
            end
        end
    end
end

Main()
