// 事件选项点击链·终局解剖：字符串引用全景 + 全量反编译关键函数 + vtable 槽表
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class EvtWin54 extends GhidraScript {
    private DecompInterface di;

    private void decomp(long addr, int cap) {
        try {
            Function f = getFunctionAt(toAddr(addr));
            if (f == null) f = getFunctionContaining(toAddr(addr));
            if (f == null) { println("(no fn 0x" + Long.toHexString(addr) + ")"); return; }
            DecompileResults res = di.decompileFunction(f, 90, monitor);
            println("==== " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " (req 0x" + Long.toHexString(addr) + ") ====");
            String[] ls = res.getDecompiledFunction().getC().split("\n");
            int n = Math.min(ls.length, cap);
            for (int i = 0; i < n; i++) println(ls[i]);
            if (ls.length > n) println("...(截断，全文 " + ls.length + " 行)");
        } catch (Exception e) { println("fail 0x" + Long.toHexString(addr) + ": " + e); }
    }

    private void xrefs(long addr, String label) {
        println("==== refs to " + label + " @0x" + Long.toHexString(addr) + " ====");
        try {
            for (Reference r : getReferencesTo(toAddr(addr))) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("  <- " + r.getFromAddress() + " " + r.getReferenceType() + " "
                        + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
            }
        } catch (Exception e) { println("  fail: " + e); }
    }

    private void dumpVtable(long base, String label, int slots) {
        println("==== vtable " + label + " @0x" + Long.toHexString(base) + " ====");
        for (int i = -2; i < slots; i++) {
            long a = base + (long) i * 8;
            try {
                long v = getLong(toAddr(a));
                String tag = "";
                if ((v >>> 32) == 0x140L || (v >>> 32) == 0x141L || (v >>> 32) == 0x142L) {
                    Function f = getFunctionContaining(toAddr(v));
                    if (f != null) tag = f.getName();
                }
                println(String.format("  [%d]\t+0x%02X\t0x%X\t%s", i, i * 8, v, tag));
            } catch (Exception e) { println("  [" + i + "] fail"); }
        }
    }

    @Override
    public void run() throws Exception {
        di = new DecompInterface();
        di.openProgram(currentProgram);
        // 1) 字符串引用全景
        xrefs(0x142323287L, "select_event_option");
        xrefs(0x142403110L, "event_option_button");
        xrefs(0x14240320BL, "coop_event_option_selected");
        xrefs(0x14240326BL, "coop_current_event_option_selected_by_other");
        xrefs(0x1424032B3L, "coop_event_option_selected_by_other");
        xrefs(0x142403238L, "event_dismiss");
        xrefs(0x142403248L, "event_close");
        xrefs(0x142403188L, "selected_event_option");
        xrefs(0x1424030E0L, "event_window_option_entry");
        // 2) 函数引用
        xrefs(0x14107b1d0L, "FUN_14107b1d0(窗口分发器)");
        xrefs(0x141c52700L, "FUN_141c52700(嵌入对象槽4)");
        xrefs(0x141c53710L, "FUN_141c53710(嵌入对象构造)");
        // 3) 全量反编译
        decomp(0x14107b1d0L, 600);
        decomp(0x141c52700L, 450);
        decomp(0x141c53710L, 220);
        decomp(0x141c53cc0L, 120);
        decomp(0x141c53170L, 80);
        decomp(0x141c52190L, 260);
        // 4) vtable 槽表
        dumpVtable(0x14257CEB0L, "嵌入对象(按钮?)", 14);
        dumpVtable(0x142403410L, "事件窗口类表A", 78);
        println("==== done EvtWin54 ====");
    }
}
