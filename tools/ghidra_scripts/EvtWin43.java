// CSelectEventOptionCommand RTTI 溯源 v2：直接引用 + .rdata 原始指针扫描 + 邻域转储
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;

public class EvtWin43 extends GhidraScript {

    private long rdq(long a) {
        try { return getLong(toAddr(a)); } catch (Exception e) { return 0; }
    }

    @Override
    public void run() throws Exception {
        println("==== 精确引用查询 ====");
        long[] strs = { 0x1428bb3beL, 0x1428bb42dL, 0x1428bb3b0L, 0x1428bb430L };
        for (long s : strs) {
            println("  引用 0x" + Long.toHexString(s) + ":");
            for (Reference r : getReferencesTo(toAddr(s))) {
                Function f = getFunctionContaining(r.getFromAddress());
                println("    <- 0x" + r.getFromAddress() + " (" + r.getReferenceType() + ")"
                        + (f != null ? " in " + f.getName() : ""));
            }
        }
        println("==== 邻域原始 qword 转储 0x1428bb340..0x1428bb4e0 ====");
        for (long a = 0x1428bb340L; a < 0x1428bb4e0L; a += 8) {
            long q = rdq(a);
            if (q != 0) {
                println("  " + Long.toHexString(a) + ": 0x" + Long.toHexString(q));
            }
        }
        println("==== .rdata 内指针扫描：指向 [0x1428bb000,0x1428bc000) 的 qword ====");
        Memory mem = currentProgram.getMemory();
        int found = 0;
        boolean stop = false;
        for (MemoryBlock b : mem.getBlocks()) {
            if (stop) break;
            if (!b.isInitialized() || b.isExecute()) continue;
            long lo = b.getStart().getOffset(), hi = b.getEnd().getOffset();
            if (hi - lo > 0x2000000L) continue;
            byte[] data = new byte[(int) Math.min(hi - lo + 1, 0x2000000)];
            try { b.getBytes(b.getStart(), data, 0, data.length); } catch (Exception e) { continue; }
            for (int i = 0; i + 8 <= data.length; i += 8) {
                long v = 0;
                for (int k = 7; k >= 0; k--) v = (v << 8) | (data[i + k] & 0xff);
                if (v >= 0x1428bb000L && v < 0x1428bc000L) {
                    println("  @0x" + Long.toHexString(lo + i) + " -> 0x" + Long.toHexString(v));
                    found++;
                    if (found > 120) { println("  (截断)"); stop = true; break; }
                }
            }
        }
        println("  共 " + found + " 处");
        println("==== done ====");
    }
}
