// Ghidra 脚本：定位控制台指令字符串的引用函数并输出反编译头部
// 用途：找"控制台执行器/指令注册" → 为"内存级调用引擎函数"铺路
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;

public class DumpConsole extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] needles = { "human_ai", "instant_build", "playme", "observe" };
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        for (String s : needles) {
            println("===== needle: " + s + " =====");
            for (Data d : currentProgram.getListing().getDefinedData(true)) {
                Object raw = d.getValue();
                if (!(raw instanceof String)) {
                    continue;
                }
                String v = (String) raw;
                if (!v.equals(s)) {
                    continue;
                }
                println("  string @ " + d.getAddress());
                for (Reference r : getReferencesTo(d.getAddress())) {
                    Function f = getFunctionContaining(r.getFromAddress());
                    println("    ref from " + r.getFromAddress() + "  in "
                            + (f != null ? f.getName() + " @" + f.getEntryPoint() : "?"));
                    if (f != null) {
                        DecompileResults res = dec.decompileFunction(f, 90, monitor);
                        if (res != null && res.decompileCompleted()) {
                            String[] lines = res.getDecompiledFunction().getC().split("\n");
                            println("    ---- decompiled head (" + lines.length + " lines) ----");
                            for (int i = 0; i < Math.min(lines.length, 350); i++) {
                                println("      " + lines[i]);
                            }
                        }
                    }
                }
            }
        }
    }
}
