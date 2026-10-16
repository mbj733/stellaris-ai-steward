// 静态检查：运行时静态指针 0x7FF6AF105078 / 0x7FF6AF1050B0 对应的映像地址
// 静态 0x1423A5078 = base(0x7FF6ACD60000) + (0x1423A5078-0x140000000)
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;

public class EvtWin45 extends GhidraScript {
    private long rdq(long a) {
        try { return getLong(toAddr(a)); } catch (Exception e) { return 0; }
    }

    private void dump(long a) {
        Address aa = toAddr(a);
        MemoryBlock b = getMemoryBlock(aa);
        String perms = b == null ? "?" : (b.isRead() ? "R" : "-") + (b.isWrite() ? "W" : "-")
                + (b.isExecute() ? "X" : "-");
        println("==== 静态 0x" + Long.toHexString(a) + "  block="
                + (b != null ? b.getName() + "(" + perms + ")" : "?"));
        for (int k = -4; k < 24; k++) {
            long q = rdq(a + k * 8L);
            if (q == 0) continue;
            String note = "";
            Function f = getFunctionAt(toAddr(q));
            if (f != null) note = "  -> " + f.getName();
            println("  [+" + String.format("%+#x", k * 8) + "] 0x" + Long.toHexString(q) + note);
        }
        println("  xrefs:");
        for (Reference r : getReferencesTo(aa)) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("    <- " + r.getFromAddress() + " " + r.getReferenceType() + " "
                    + (f != null ? f.getName() + "@" + f.getEntryPoint() : "?"));
        }
    }

    @Override
    public void run() throws Exception {
        dump(0x1423A5078L);
        dump(0x1423A50B0L);
        println("==== done ====");
    }
}
