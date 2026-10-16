// (a) 打印 0x1422fdf80~0x1422fe0e0 区间的字符串字面量
// (b) 反编译读取 [0x1431146f9] 的一个代表函数，确认该标志含义
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class DumpLits extends GhidraScript {
    @Override
    public void run() throws Exception {
        println("==== strings in 1422fdf80..1422fe0e0 ====");
        Address a = toAddr(0x1422fdf80L);
        Address end = toAddr(0x1422fe0e0L);
        while (a != null && a.getOffset() < end.getOffset()) {
            Data d = getDataAt(a);
            if (d != null && d.hasStringValue()) {
                println("  " + a + " = " + d.getValue());
            }
            a = a.add(1);
        }
        println("==== readers of 0x1431146f9 (up to 6) ====");
        int shown = 0;
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        for (Reference r : getReferencesTo(toAddr(0x1431146f9L))) {
            if (shown >= 6) {
                break;
            }
            Function f = getFunctionContaining(r.getFromAddress());
            if (f == null) {
                continue;
            }
            println("--- reader in " + f.getName() + " @" + f.getEntryPoint());
            DecompileResults res = dec.decompileFunction(f, 60, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                int n = 0;
                for (String l : lines) {
                    if (l.contains("1431146f9") || l.contains("DAT_1431146f9")) {
                        println("      >> " + l.trim());
                        n++;
                        if (n >= 3) {
                            break;
                        }
                    }
                }
            }
            shown++;
        }
        println("==== done ====");
    }
}
