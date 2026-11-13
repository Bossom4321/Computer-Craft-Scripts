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




function printPage(content,title,MAXWIDTH,MAXHIGHT)
    checkLevels()
    local maxWidth = 25  
    local maxHight = 25
    local TITLE = "Unnamed"
    if MAXWIDTH ~= nil then maxWidth = MAXWIDTH end
    if MAXHIGHT ~= nil then maxHight = MAXHIGHT+1 end
    if title ~= nil then TITLE = title end
    title = TITLE
    printer.newPage()
    local pagecount = 1
    local count = 1

        printer.setPageTitle(title.." "..pagecount)
    for i = 1, string.len(content) do
    checkLevels()
        
        local char = string.sub(content, i, i)
        if i % maxWidth == 0 then
            count = count + 1
            if maxHight == count then
                while not printer.endPage() do
                    
                    print("Printer output full waiting.....")
                    sleep(0.5)
                end
                checkLevels()
                printer.newPage()
                pagecount = pagecount + 1
                printer.setPageTitle(title.." "..pagecount)
                count = 1
            end
            printer.setCursorPos(1,count)
        end
        printer.write(char)
    end

    printer.endPage()

    
end

