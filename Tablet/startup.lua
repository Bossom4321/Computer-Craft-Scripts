package.path = package.path .. ";.apis/?.lua"
require("displaymanager")
require("todo")
programs = {"To-Do List"}


while true do
    term.clear()
    term.setCursorPos(1,1)
    outnl("Enter The Number Of the Program:")
    for i=1, #programs do
        out(i..": ")
        outnl(programs[i])
    end

    userinp = read()
    if tonumber(userinp) then
        userinp = tonumber(userinp)
        if (userinp > #programs) or (userinp < 0) then
            term.clear()
            outnl("Invalid selection")
        elseif userinp == 1 then
            todoMain()
        end




    else
        term.clear()
        outnl("Enter Only The Number")
    end
end