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


function printImageDither(image,peripherial,xpos,ypos, ditherchar,sleepd)
    sleepd = sleepd or 0.01
    function readPairsPerLine(path)
    local f = fs.open(path, "r")
    if not f then error("Could not open file: " .. tostring(path)) end

    local result = {}
    local hex = nil

    -- helper: first pass, expand PAIRPAIRxN+ into stage1 string
    local function expand_pairs(line)
        local out = {}
        local i = 1
        local n = #line

        while i <= n do
            -- Try to match PAIRPAIRxN+  (a b a b x digits [+]?)
            if i + 4 <= n then
                local a  = line:sub(i,   i)
                local b  = line:sub(i+1, i+1)
                local a2 = line:sub(i+2, i+2)
                local b2 = line:sub(i+3, i+3)
                local x  = line:sub(i+4, i+4)

                if a == a2 and b == b2 and x == "x" then
                    -- read digits after 'x'
                    local j = i + 5
                    while j <= n and line:sub(j,j):match("%d") do
                        j = j + 1
                    end

                    local num_str = line:sub(i+5, j-1)
                    local num = tonumber(num_str)
                    if num then
                        local sep = (line:sub(j,j) == "+") and 1 or 0
                        local total = num + 2  -- N+2 pairs

                        for _ = 1, total do
                            table.insert(out, a)
                            table.insert(out, b)
                        end

                        i = j + sep
                        goto continue_pairs
                    end
                end
            end

            -- no pair token, copy raw char
            table.insert(out, line:sub(i,i))
            i = i + 1

            ::continue_pairs::
        end

        return table.concat(out)
    end

    -- helper: second pass, expand ccxN- into fully uncompressed string
    local function expand_singles(line)
        local out = {}
        local i = 1
        local n = #line

        while i <= n do
            -- Try to match ccxN- (single char RLE)
            if i + 3 <= n then
                local c1 = line:sub(i,   i)
                local c2 = line:sub(i+1, i+1)
                local x  = line:sub(i+2, i+2)

                if c1 == c2 and x == "x" then
                    local j = i + 3
                    while j <= n and line:sub(j,j):match("%d") do
                        j = j + 1
                    end

                    local num_str = line:sub(i+3, j-1)
                    local num = tonumber(num_str)
                    if num then
                        local sep = (line:sub(j,j) == "-") and 1 or 0
                        local total = num + 2  -- N+2 characters

                        for _ = 1, total do
                            table.insert(out, c1)
                        end

                        i = j + sep
                        goto continue_singles
                    end
                end
            end

            -- no single-char token, copy raw char
            table.insert(out, line:sub(i,i))
            i = i + 1

            ::continue_singles::
        end

        return out
    end

    -- Read first line and check for palette header
    local first_line = f.readLine()
    if not first_line then
        f.close()
        return result, hex
    end

    if first_line:sub(1,2) == "0x" then
        -- parse comma-separated hex values into 'hex' table as numbers
        hex = {}
        for token in first_line:gmatch("([^,]+)") do
            token = token:match("^%s*(.-)%s*$") -- trim whitespace
            if token ~= "" then
                local val = nil
                if token:sub(1,2):lower() == "0x" then
                    -- try tonumber directly (Lua 5.3+ supports 0x), fallback to base-16 parse
                    val = tonumber(token)
                    if not val then
                        local hexpart = token:sub(3)
                        val = tonumber(hexpart, 16)
                    end
                else
                    -- not prefixed with 0x, try decimal then hex fallback
                    val = tonumber(token)
                    if not val then
                        val = tonumber(token, 16)
                    end
                end
                if val then
                    table.insert(hex, val)
                else
                    -- if parsing fails, insert 0 as a safe fallback
                    table.insert(hex, 0)
                end
            end
        end
        -- continue reading from line 2 onwards
    else
        -- first line is not a palette header: treat it as a pixel line
        -- 1) undo pair compression
        local stage1 = expand_pairs(first_line)
        -- 2) undo single-char compression
        local expanded = expand_singles(stage1)
        -- 3) ensure even count
        if (#expanded % 2) == 1 then
            table.insert(expanded, "0")
        end
        -- 4) split into 2-character pairs
        local pairs = {}
        for k = 1, #expanded, 2 do
            table.insert(pairs, expanded[k] .. expanded[k+1])
        end
        table.insert(result, pairs)
    end

    -- Process remaining lines
    while true do
        local line = f.readLine()
        if not line then break end

        -- 1) undo pair compression
        local stage1 = expand_pairs(line)

        -- 2) undo single-char compression
        local expanded = expand_singles(stage1)

        -- 3) ensure even count
        if (#expanded % 2) == 1 then
            table.insert(expanded, "0")
        end

        -- 4) split into 2-character pairs
        local pairs = {}
        for k = 1, #expanded, 2 do
            table.insert(pairs, expanded[k] .. expanded[k+1])
        end

        table.insert(result, pairs)
    end

    f.close()
    return result, hex
end



image,hex = readPairsPerLine(image)
setPalette(peripherial,hex)
peripherial = peripherial or term
xpos = xpos or 1
ypos = ypos or 1
ditherchar = ditherchar or string.char(127)
curs = ypos
peripherial.clear()
for i=1,#image do
    peripherial.setCursorPos(xpos,curs)
    for z=1,#image[i] do
        local idx = findindex(colorsid, string.sub(image[i][z],1,1):lower())
        local idx2 = findindex(colorsid, string.sub(image[i][z],2,2):lower())
        if idx and idx2 then
        out(ditherchar, peripherial, colornum(colors[idx2]), colornum(colors[idx]))
        end
        outnl("",term)
    end
    outnl()
    curs = curs+1
    if sleepd > 0 and i%20 == 0 then
    sleep(sleepd)
    end
end
end


function printImageDitherHex(image,peripherial,xpos,ypos, ditherchar,sleepd)
    sleepd = sleepd or 0.01
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

    -- 2. Read marker
    f.readLine()

    -- 3. Skip 3 blank lines
    f.readLine()
    f.readLine()
    f.readLine()

    -- 4. Read ALL remaining bytes as binary
    local data = f.readAll()
    f.close()

    -- Convert to byte array
    local bytes = { string.byte(data, 1, #data) }

    local rows = {}
local current = {}

local i = 1
while i <= #bytes do
    local b = bytes[i]
    local b2 = bytes[i+1]

-- row terminator FF 00
        if b == 0xFF and b2 == 0x00 then
            table.insert(rows, current)
            current = {}
            i = i + 2
        else
            table.insert(current, b)
            table.insert(current, b2) -- Insert the count byte
            i = i + 2                 -- Advance by 2 to read the next pair
        end
    end


    -- 5. Decode each row
    for _, row in ipairs(rows) do
        local out = {}
        local i = 1
        while i <= #row do
            local value = row[i]
            local count = row[i+1]
            if not count then break end

            local bg = math.floor(value / 16)
            local fg = value % 16

            for _ = 1, count do
                table.insert(out, string.format("%x%x", bg, fg))
            end

            i = i + 2
        end
        table.insert(result, out)
    end

    return result, hex
end




image,hex = readPairsPerLine(image)
setPalette(peripherial,hex)
peripherial = peripherial or term
xpos = xpos or 1
ypos = ypos or 1
ditherchar = ditherchar or string.char(127)
curs = ypos
peripherial.clear()
for i=1,#image do
    peripherial.setCursorPos(xpos,curs)
    for z=1,#image[i] do
        local idx = findindex(colorsid, string.sub(image[i][z],1,1):lower())
        local idx2 = findindex(colorsid, string.sub(image[i][z],2,2):lower())
        if idx and idx2 then
        out(ditherchar, peripherial, colornum(colors[idx2]), colornum(colors[idx]))
        end
        outnl("",term)
    end
    outnl()
    curs = curs+1
    if sleepd > 0 and i%20 == 0 then
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
peripherial.clear()
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