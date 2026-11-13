require("displaymanager")

local colorsid = {"0","1","2","3","4","5","6","7","8","9","a","b","c","d","e","f"}
local colors = {"white","orange","magenta","lightblue", "yellow", "lime","pink","gray","lightgray","cyan","purple","blue","brown","green","red","black"}

function setPalette(peripherial,palette)
    palette = palette or {0xF0F0F0,0xF2B233,0xE57FD8,0x99B2F2,0xDEDE6C,0x7FCC19,0xF2B2CC,0x4C4C4C,0x999999,0x4C99B2,0xB266E5,0x3366CC,0x7F664C,0x57A64E,0xCC4C4C,0x111111}
    for x =0,15 do
        peripherial.setPaletteColor(2^(x),palette[x+1])
    end
end

function vibrant(peripherial)
    vibhex = {
        0xFFFFFF, -- white
        0xFFA500, -- orange
        0xFF00FF, -- magenta
        0xADD8E6, -- lightblue
        0xFFFF00, -- yellow
        0x00FF00, -- lime
        0xFFC0CB, -- pink
        0x808080, -- gray
        0xD3D3D3, -- lightgray
        0x00FFFF, -- cyan
        0x800080, -- purple
        0x0000FF, -- blue
        0xA52A2A, -- brown
        0x008000, -- green
        0xFF0000, -- red
        0x000000 -- black
    }

for x=1,16 do
    peripherial.setPaletteColor(2^(x-1),vibhex[x])
end  
end











local function readCharsPerLine(path)

  local f = fs.open(path, "r")
  if not f then error("Could not open file: " .. tostring(path)) end

  local result = {}
  local line = {}
  while true do
    local ch = f.read(number)
    if ch == nil then
      -- EOF: push last line if it has content (or even if empty, to preserve final newline)
      if #line > 0 then table.insert(result, line) end
      break
    end
    if ch == "\n" then
      table.insert(result, line)
      line = {}
    else
      table.insert(line, ch)
    end
  end

  f.close()
  return result
end


function printImageDither(image, peripherial, xpos, ypos, ditherchar, sleepd)
    sleepd = sleepd or 0.01

    function readPairsPerLine(path)
        local f = fs.open(path, "r")
        if not f then error("Could not open file: " .. tostring(path)) end

        local result = {}
        local hex = nil

        -- Helper: Decompress a line directly into continuous color runs
        local function decompress_line(line)
            -- 1) undo pair compression (e.g., ababx5+) instantly using regex
            local stage1 = line:gsub("(.)(.)%1%2x(%d+)%+?", function(c1, c2, num_str)
                return string.rep(c1 .. c2, tonumber(num_str) + 2)
            end)

            -- 2) undo single-char compression (e.g., aax3-) instantly using regex
            local expanded = stage1:gsub("(.)%1x(%d+)%-?", function(c1, num_str)
                return string.rep(c1, tonumber(num_str) + 2)
            end)

            -- 3) ensure even count
            if (#expanded % 2) == 1 then
                expanded = expanded .. "0"
            end

            -- 4) Group directly into RLE runs instead of making thousands of pairs
            local runs = {}
            local curBg, curFg, runLen = nil, nil, 0

            for k = 1, #expanded, 2 do
                -- Grab lowercase bg/fg directly
                local bg = expanded:sub(k, k):lower()
                local fg = expanded:sub(k + 1, k + 1):lower()

                if bg == curBg and fg == curFg then
                    runLen = runLen + 1
                else
                    if runLen > 0 then
                        table.insert(runs, {bg = curBg, fg = curFg, count = runLen})
                    end
                    curBg = bg
                    curFg = fg
                    runLen = 1
                end
            end
            
            -- Flush the last run
            if runLen > 0 then
                table.insert(runs, {bg = curBg, fg = curFg, count = runLen})
            end

            return runs
        end

        -- Read first line and check for palette header
        local first_line = f.readLine()
        if not first_line then
            f.close()
            return result, hex
        end

        if first_line:sub(1, 2) == "0x" then
            -- parse comma-separated hex values into 'hex' table as numbers
            hex = {}
            for token in first_line:gmatch("([^,]+)") do
                token = token:match("^%s*(.-)%s*$") -- trim whitespace
                if token ~= "" then
                    local val = nil
                    if token:sub(1, 2):lower() == "0x" then
                        val = tonumber(token)
                        if not val then
                            val = tonumber(token:sub(3), 16)
                        end
                    else
                        val = tonumber(token)
                        if not val then
                            val = tonumber(token, 16)
                        end
                    end
                    table.insert(hex, val or 0)
                end
            end
        else
            -- First line is not a palette, process it as image data
            table.insert(result, decompress_line(first_line))
        end

        -- Process remaining lines
        while true do
            local line = f.readLine()
            if not line then break end
            table.insert(result, decompress_line(line))
        end

        f.close()
        return result, hex
    end

    image, hex = readPairsPerLine(image)
    if hex then setPalette(peripherial, hex) end
    
    peripherial = peripherial or term
    xpos = xpos or 1
    ypos = ypos or 1
    ditherchar = ditherchar or string.char(127)
    local curs = ypos
    --peripherial.clear()

    -- Cache color lookups to avoid doing string/math conversions for every pixel
    local colorCache = {}
    local function getCCColorCached(hexChar)
        if colorCache[hexChar] == nil then
            local idx = findindex(colorsid, hexChar)
            if idx then
                colorCache[hexChar] = colornum(colors[idx])
            else
                colorCache[hexChar] = false
            end
        end
        return colorCache[hexChar] or nil
    end

    -- Drawing Loop
    for i = 1, #image do
        peripherial.setCursorPos(xpos, curs)
        
        -- We now iterate over large color runs instead of individual pairs
        for z = 1, #image[i] do
            local run = image[i][z]
            local bgVal = getCCColorCached(run.bg)
            local fgVal = getCCColorCached(run.fg)
            
            if bgVal and fgVal then
                out(string.rep(ditherchar, run.count), peripherial, fgVal, bgVal)
            end
        end
        
        outnl()
        curs = curs + 1
        if sleepd > 0 and i % 20 == 0 then
            sleep(sleepd)
        end
    end
end


function printImageDitherHex(image, peripherial, xpos, ypos, ditherchar, sleepd)
    sleepd = sleepd or 0
    
    function readPairsPerLine(path)
        local f = fs.open(path, "rb")
        if not f then error("Could not open file: " .. tostring(path)) end

        local result = {}
        local hex = {}

        -- 1. Read palette line (text)
        local palette_line = f.readLine()
        for token in palette_line:gmatch("([^,]+)") do
            token = token:match("^%s*(.-)%s*$")
            local val = tonumber(token) or tonumber(token:sub(3), 16)
            table.insert(hex, val)
        end

        -- 2. Read marker & 3. Skip 3 blank lines
        f.readLine()
        f.readLine()
        f.readLine()
        f.readLine()

        -- 4. Read ALL remaining bytes as binary
        local data = f.readAll()
        f.close()

        -- 5. Decode RLE data DIRECTLY into runs
        local rows = {}
        local currentRow = {}
        local i = 1
        local len = #data
        
        -- Using an index avoids Lua's "too many return values" limit crash
        while i < len do
            local b1, b2 = string.byte(data, i, i+1)
            if not b2 then break end

            -- row terminator FF 00
            if b1 == 0xFF and b2 == 0x00 then
                table.insert(rows, currentRow)
                currentRow = {}
                i = i + 2
            else
                -- Extract colors to strings directly here, skipping string.sub later
                local bg_hex = string.format("%x", math.floor(b1 / 16))
                local fg_hex = string.format("%x", b1 % 16)
                
                -- Store the RLE run instead of expanding it into single pixels
                table.insert(currentRow, { bg = bg_hex, fg = fg_hex, count = b2 })
                i = i + 2
            end
        end
        
        if #currentRow > 0 then table.insert(rows, currentRow) end

        return rows, hex
    end

    image, hex = readPairsPerLine(image)
    setPalette(peripherial, hex)
    peripherial = peripherial or term
    xpos = xpos or 1
    ypos = ypos or 1
    ditherchar = ditherchar or string.char(127)
    local curs = ypos
    --peripherial.clear()

    -- Cache color lookups so we only calculate each of the 16 colors once!
    local colorCache = {}
    local function getCCColorCached(hexChar)
        if colorCache[hexChar] == nil then
            local idx = findindex(colorsid, hexChar)
            if idx then
                colorCache[hexChar] = colornum(colors[idx])
            else
                colorCache[hexChar] = false -- Cache failures too
            end
        end
        return colorCache[hexChar] or nil
    end

    -- Draw straight from the RLE chunks
    for i = 1, #image do
        peripherial.setCursorPos(xpos, curs)
        
        for z = 1, #image[i] do
            local run = image[i][z]
            local bgVal = getCCColorCached(run.bg)
            local fgVal = getCCColorCached(run.fg)
            
            if bgVal and fgVal then
                out(string.rep(ditherchar, run.count), peripherial, fgVal, bgVal)
            end
        end
        
        outnl()
        curs = curs + 1
        if sleepd > 0 and i % 20 == 0 then
            sleep(sleepd)
        end
    end
end


function printImage(image,peripherial,xpos,ypos)
image = readCharsPerLine(image)
peripherial = peripherial or term
xpos = xpos or 1
ypos = ypos or 1
curs = ypos
--peripherial.clear()
for i=1,#image do
    peripherial.setCursorPos(xpos,curs)
    for z=1,#image[i] do
        local idx = findindex(colorsid, image[i][z]:lower())
        if idx then
        out(" ", peripherial, "black", colornum(colors[idx]))
        end
        outnl("",term)
    end
    outnl()
    curs = curs+1
end
end