function slice(tbl, first, last)
  local result = {}
  for i = first, last do
    table.insert(result, tbl[i])
  end
  return result
end

function findindex(table, what)
  for i = 1, #table do
    if table[i] == what then
      return i
    end
  end
  return false
end

function isin(table, what)
  for i = 1, #table do
    if table[i] == what then
      return true
    end
  end
  return false
end

function sortByLetter(tbl)
  local temp = {}
  for i = 1, #tbl do
    temp[i] = tbl[i]
  end
  table.sort(temp, function(a, b)
    return a:lower() < b:lower()
  end)
  return temp
end

function sortByNumberPart(tbl)
  table.sort(tbl, function(a, b)
    local numA = tonumber(a:match("%d+"))
    local numB = tonumber(b:match("%d+"))
    return numA < numB
  end)
  return tbl
end

function sortNumberList(tbl)
  table.sort(tbl, function(a, b) return a < b end)
  return tbl
end

local function trim(s)
  return (s:gsub("^%s*(.-)%s*$", "%1"))
end

local function parseCSVLine(line)
  local fields = {}
  local i = 1
  local len = #line
  while i <= len do
    local c = line:sub(i, i)
    local field = ""

    if c == '"' then
      -- quoted field
      i = i + 1
      while i <= len do
        local ch = line:sub(i, i)
        if ch == '"' then
          -- look ahead for escaped quote
          if line:sub(i + 1, i + 1) == '"' then
            field = field .. '"'
            i = i + 2
          else
            i = i + 1
            break
          end
        else
          field = field .. ch
          i = i + 1
        end
      end
      -- skip optional spaces then comma
      while i <= len and line:sub(i, i) ~= "," do
        if line:sub(i, i):match("%s") then
          i = i + 1
        else
          break
        end
      end
      if line:sub(i, i) == "," then i = i + 1 end
    else
      -- unquoted field
      while i <= len and line:sub(i, i) ~= "," do
        field = field .. line:sub(i, i)
        i = i + 1
      end
      if line:sub(i, i) == "," then i = i + 1 end
      field = trim(field)
    end

    table.insert(fields, field)
  end
  return fields
end

function readCSV(path)
  local rows = {}
  if not fs.exists(path) then
    error("File not found: " .. path)
  end

  local f = fs.open(path, "r")
  if not f then error("Could not open file: " .. path) end

  while true do
    local line = f.readLine()
    if not line then break end
    -- skip empty lines (optional)
    if line:match("%S") then
      local parsed = parseCSVLine(line)
      table.insert(rows, parsed)
    end
  end

  f.close()
  return rows
end
