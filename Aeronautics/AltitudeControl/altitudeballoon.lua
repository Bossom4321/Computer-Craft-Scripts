-- Wrap Peripherals
package.path = package.path .. ";.apis/?.lua"
require("rsapi")
local altisens = peripheral.wrap("back")
local burner = peripheral.wrap("top")

-- Physics Constants
local gravity = 9
local lift_multiplier = 0.1198
local loop_time = 0.1 -- dt (delta time)
local burner_rs_side = "top" -- Adjust if needed

-- Controller Tuning Variables
local Kp = 5.0  -- Proportional: Push strength
local Kd = 35.0 -- Derivative: Brakes 
local Ki = 1.0  -- Integral: Long-term error corrector

-- Global Variables
local integral_sum = 0 
local targetalti = 0
local input = ""
local saveFile = "altitude_save.txt"

----------------------------------------
-- 1. Persistence Functions
----------------------------------------
local function saveAltitude(alt)
    local f = fs.open(saveFile, "w")
    if f then
        f.write(tostring(alt))
        f.close()
    end
end

local function loadAltitude()
    if fs.exists(saveFile) then
        local f = fs.open(saveFile, "r")
        if f then
            local data = f.readAll()
            f.close()
            local num = tonumber(data)
            if num then return num end
        end
    end
    return nil
end

-- Initialize Altitude Setting
local savedAlt = loadAltitude()
if savedAlt then
    targetalti = savedAlt
else
    term.clear()
    term.setCursorPos(1,1)
    print("No save found. Enter Initial Target Altitude:")
    targetalti = tonumber(read()) or 100 -- fallback to 100 if invalid input
    saveAltitude(targetalti)
end

----------------------------------------
-- 2. User Interface & Input Coroutine
----------------------------------------
local function drawUI()
    term.clear()
    term.setCursorPos(1, 1)
    print("=== Flight Controller Active ===")
    print("Target Altitude : " .. targetalti)
    print("Current Altitude: " .. (math.floor(altisens.getHeight() * 10) / 10))
    
    term.setCursorPos(1, 5)
    term.write("Enter new altitude: " .. input)
end

local function inputLoop()
    while true do
        drawUI()
        local event, p1 = os.pullEvent()

        if event == "char" then
            -- Allow numbers and a minus sign for negative coordinates
            if p1:match("[%d%-]") then 
                input = input .. p1
            end
        elseif event == "key" then
            if p1 == keys.backspace then
                input = input:sub(1, -2)
            elseif p1 == keys.enter then
                local new_alt = tonumber(input)
                if new_alt then
                    targetalti = new_alt
                    saveAltitude(targetalti)
                    integral_sum = 0 -- Reset integral when target changes to prevent sudden jolts
                end
                input = ""
            end
        end
    end
end

----------------------------------------
-- 3. Physics & Control Coroutine
----------------------------------------
local function controlLoop()
    while true do
        -- Read Current State
        -- (Assuming sublevel is defined globally or injected by an API)
        local mass = sublevel.getMass()
        local current_alti = altisens.getHeight()
        local vertical_speed = altisens.getVerticalSpeed()
        
        -- Calculate Base Equilibrium Product
        local hover_product = ((mass * gravity) / lift_multiplier) * (2 / 15)
        
        -- Calculate Distance to Target
        local error = targetalti - current_alti
        
        -- ANTI-WINDUP FIX
        if math.abs(error) < 50 then
            integral_sum = integral_sum + (error * loop_time)
            -- Clamped to prevent infinite pressure
            integral_sum = math.max(-2000, math.min(2000, integral_sum))
        else
            integral_sum = 0 
        end
        
        -- PID Calculation
        local adjustment = (Kp * error) + (Ki * integral_sum) - (Kd * vertical_speed)
        local adjustment_product = adjustment * 2
        
        -- Total lift effort required
        local target_product = hover_product + adjustment_product
        
        -- Apply the output
        if target_product <= 0 then
            rOut(burner_rs_side, 0)
            burner.setTargetAmount(5) 
        else
            local required_rs = math.ceil(target_product / 500)
            local rs_signal = math.max(1, math.min(15, required_rs))
            
            local output_amount = target_product / rs_signal
            output_amount = math.max(5, math.min(500, output_amount))
            
            rOut(burner_rs_side, rs_signal)
            burner.setTargetAmount(output_amount)
        end
        
        -- Re-draw UI occasionally so current altitude updates smoothly
        -- (The UI will normally redraw on keystrokes, but this keeps it live)
        drawUI()
        
        os.sleep(loop_time)
    end
end

----------------------------------------
-- 4. Start Parallel Execution
----------------------------------------
-- waitForAny means if either loop crashes or finishes, the script stops safely.
parallel.waitForAny(inputLoop, controlLoop)