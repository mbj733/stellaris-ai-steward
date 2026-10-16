// 事件实例类方法解剖 + 嵌入处理器 vtable 槽位反编译
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin51 extends GhidraScript {
    private DecompInterface di;

    private void decomp(long addr, int cap) {
        try {
            Function f = getFunctionAt(toAddr(addr));
            if (f == null) { println("(no fn 0x" + Long.toHexString(addr) + ")"); return; }
            DecompileResults res = di.decompileFunction(f, 60, monitor);
            println("==== " + f.getName() + " @0x" + Long.toHexString(addr) + " ====");
            String[] ls = res.getDecompiledFunction().getC().split("\n");
            for (int i = 0; i < Math.min(ls.length, cap); i++) println(ls[i]);
        } catch (Exception e) { println("fail 0x" + Long.toHexString(addr) + ": " + e); }
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        println("==== refs to eventData vtable 0x1423A5078（找构造函数）====");
        for (Reference r : getReferencesTo(toAddr(0x1423A5078L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  <- " + r.getFromAddress() + " " + r.getReferenceType() + " "
                    + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
        println("==== refs to 0x1423A50B0 ====");
        for (Reference r : getReferencesTo(toAddr(0x1423A50B0L))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  <- " + r.getFromAddress() + " " + r.getReferenceType() + " "
                    + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
        // A: 事件实例 vtable 方法
        decomp(0x1408e4d90L, 55);
        decomp(0x14050dc70L, 55);
        decomp(0x1408e6c70L, 55);
        decomp(0x1408e85c0L, 55);
        decomp(0x1408eae70L, 55);
        decomp(0x1408e2850L, 55);
        decomp(0x1408e2950L, 55);
        decomp(0x1408e2ce0L, 55);
        decomp(0x1408e2e20L, 55);
        // B: 嵌入处理器 vtable 方法
        decomp(0x141c53b60L, 45);
        decomp(0x141c055c0L, 45);
        decomp(0x141c52700L, 45);
        decomp(0x141c52190L, 45);
        decomp(0x141c53170L, 45);
        decomp(0x141c53cc0L, 45);
        println("==== done ====");
    }
}
