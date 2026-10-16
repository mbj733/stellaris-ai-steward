// 关键静态结构：嵌入命令对象 vtable 0x14257CEB0、事件数据 vtable 0x1423A5078 / 0x1423A50B0、
// 窗口[0] 指向 0x142403550 附近区段
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;

public class EvtWin46 extends GhidraScript {
    private long rdq(long a) {
        try { return getLong(toAddr(a)); } catch (Exception e) { return 0; }
    }

    private void dump(String tag, long a, int slots) {
        MemoryBlock b = getMemoryBlock(toAddr(a));
        println("==== " + tag + " 0x" + Long.toHexString(a) + "  block="
                + (b != null ? b.getName() : "?"));
        for (int k = -2; k < slots; k++) {
            long q = rdq(a + k * 8L);
            if (q == 0) { continue; }
            Function f = getFunctionAt(toAddr(q));
            println("  [" + k + "] 0x" + Long.toHexString(q)
                    + (f != null ? "  " + f.getName() : ""));
        }
    }

    @Override
    public void run() throws Exception {
        dump("嵌入对象 vtable?", 0x14257CEB0L, 24);
        dump("事件数据 vtable A", 0x1423A5078L, 24);
        dump("事件数据 vtable B", 0x1423A50B0L, 24);
        dump("窗口[0] 目标区", 0x142403540L, 32);
        println("==== done ====");
    }
}
