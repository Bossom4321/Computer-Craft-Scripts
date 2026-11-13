
---printer documentation below
---* means optional and has default fallback
---printPage(content,*title,*maxpagewidth,*maxpagehight)
---
---
---
---
---
---
---
printer = peripheral.find("printer")

function outP(text, linex, liney)
    text = text or ""
    text = tostring(text)
    local x, y = printer.getCursorPos()
    linex = linex or x
    liney = liney or y

    printer.setCursorPos(linex, liney)
    printer.write(text)
end

function checkLevels()
    while printer.getPaperLevel() == 0 do
        print("Insert Paper To Continue.....")
        sleep(0.5)
    end
    while printer.getInkLevel() == 0 do
        print("Insert Ink To Continue.....")
        sleep(0.5)
    end
end

function harvester(text, max_len)
    -- 1. Check for newlines (\n or \r) BEFORE or AT our max_len limit
    local nl_pos = text:find("[\r\n]")
    
    if nl_pos and nl_pos <= max_len + 1 then
        -- Handle \r\n pairs seamlessly
        local next_start = nl_pos + 1
        if text:sub(nl_pos, nl_pos + 1) == "\r\n" then
            next_start = nl_pos + 2
        end
        return text:sub(1, nl_pos - 1), text:sub(next_start), true
    end

    -- 2. If the text fits entirely within max_len, return it
    if #text <= max_len then
        return text, "", false
    end

    -- 3. Check for clean word breaks (spaces)
    if text:sub(max_len + 1, max_len + 1) == " " then
        return text:sub(1, max_len), text:sub(max_len + 2), false
    end

    local chunk = text:sub(1, max_len)
    local space_pos = chunk:match(".*() ")
    
    if space_pos then
        return text:sub(1, space_pos - 1), text:sub(space_pos + 1), false
    end

    -- 4. Fallback: Force-chop long words that exceed max_len
    return text:sub(1, max_len), text:sub(max_len + 1), false
end

function printPage(content, title, MAXWIDTH, MAXHIGHT)
    checkLevels()

    local maxWidth = MAXWIDTH or 25
    local maxHeight = (MAXHIGHT or 20) + 1
    local TITLE = title or "Unnamed"
    local contemp = content or ""

    local function newPage(pagecount)
        while not printer.newPage() do
            sleep(0.5)
        end
        printer.setPageTitle(TITLE .. " " .. pagecount)
    end

    local page = 1
    local line = 1

    newPage(page)

    while contemp ~= "" do
        local wri, hitNewline
        wri, contemp, hitNewline = harvester(contemp, maxWidth)
        
        if wri ~= nil then
            outP(wri, 1, line)
        end
        
        -- Advance exactly 1 line down the paper for each row printed
        line = line + 1

        -- Start new page if height limit reached
        if line == maxHeight and contemp ~= "" then
            while not printer.endPage() do
                print("Printer output full. Waiting...")
                sleep(0.5)
            end
            checkLevels()
            page = page + 1
            newPage(page)
            line = 1
        end
    end

    while not printer.endPage() do
        print("Printer output full. Waiting...")
        sleep(0.5)
    end
    sleep(0.01)
end



function printPageold(content, title, MAXWIDTH, MAXHIGHT)
    checkLevels()

    local maxWidth = MAXWIDTH or 25
    local maxHeight = (MAXHIGHT or 20) + 1
    local TITLE = title or "Unnamed"

    local words = {}
    for word in string.gmatch(content, "%S+") do
        table.insert(words, word)
    end

    local function newPage(pagecount)
        while not printer.newPage() do
            sleep(0.5)
        end
        printer.setPageTitle(TITLE .. " " .. pagecount)
    end

    local page = 1
    local line = 1
    local lineBuffer = ""

    newPage(page)

    for i, word in ipairs(words) do
        if #lineBuffer + #word + 1 <= maxWidth and word ~= "\n" then
            if lineBuffer == "" then
                lineBuffer = word
            else
                lineBuffer = lineBuffer .. " " .. word
            end
        else
            printer.setCursorPos(1, line)
            printer.write(lineBuffer)
            line = line + 1

            -- Start new page if height limit reached
            if line == maxHeight then
                while not printer.endPage() do
                    print("Printer output full. Waiting...")
                    sleep(0.5)
                end
                checkLevels()
                page = page + 1
                newPage(page)
                line = 1
            end

            lineBuffer = word  -- Start new line with overflow word
        end
    end

    -- Print any remaining text
    if lineBuffer ~= "" then
        printer.setCursorPos(1, line)
        printer.write(lineBuffer)
    end

    while not printer.endPage() do
        print("Printer output full. Waiting...")
        sleep(0.5)
    end
    sleep(0.01)
end
