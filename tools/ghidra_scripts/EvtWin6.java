// EvtWin6: 标志位全量引用（含表内裸指针）+ 设置块结构 + getter 函数
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class EvtWin6 extends GhidraScript {

    List<Long> findPattern(byte[] pat) throws Exception {
        List<Long> hits = new ArrayList<>();
        int keep = pat.length - 1;
        for (MemoryBlock blk : currentProgram.getMemory().getBlocks()) {
            if (!blk.isInitialized()) {
                continue;
            }
            long start = blk.getStart().getOffset();
            long end = blk.getEnd().getOffset();
            int chunk = 1 << 22;
            byte[] buf = new byte[chunk];
            byte[] carry = new byte[0];
            long pos = start;
            outer:
            while (pos <= end) {
                int want = (int) Math.min(chunk, end - pos + 1);
                int got;
                try {
                    got = blk.getBytes(toAddr(pos), buf, 0, want);
                } catch (Exception e) {
                    break;
                }
                if (got <= 0) {
                    break;
                }
                byte[] data = new byte[carry.length + got];
                System.arraycopy(carry, 0, data, 0, carry.length);
                System.arraycopy(buf, 0, data, carry.length, got);
                long baseVa = pos - carry.length;
                for (int i = 0; i + pat.length <= data.length; i++) {
                    boolean ok = true;
                    for (int j = 0; j < pat.length; j++) {
                        if (data[i + j] != pat[j]) {
                            ok = false;
                            break;
                        }
                    }
                    if (ok) {
                        hits.add(baseVa + i);
                        if (hits.size() > 200) {
                            break outer;
                        }
                    }
                }
                if (got < want) {
                    break;
                }
                pos += got;
                int k = Math.min(keep, data.length);
                carry = Arrays.copyOfRange(data, data.length - k, data.length);
            }
        }
        return hits;
    }

    byte[] leq(long v, int n) {
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) {
            b[i] = (byte) ((v >>> (8 * i)) & 0xff);
        }
        return b;
    }

    void scanAddr(long va, String label) throws Exception {
        int rva = (int) (va - currentProgram.getImageBase().getOffset());
        System.out.println("==== refs to " + label + " 0x" + Long.toHexString(va) + " (raw scan) ====");
        List<Long> q = findPattern(leq(va, 8));
        System.out.println("  full-qword hits: " + q.size());
        for (long h : q) {
            System.out.println("    @0x" + Long.toHexString(h));
        }
        List<Long> d = findPattern(leq(rva & 0xffffffffL, 4));
        System.out.println("  rva-dword hits: " + d.size());
        int shown = 0;
        for (long h : d) {
            if (shown++ >= 12) {
                System.out.println("    ...");
                break;
            }
            System.out.println("    @0x" + Long.toHexString(h));
        }
    }

    void decompileFn(long va, int cap) {
        Function f = getFunctionContaining(toAddr(va));
        if (f == null) {
            println("  (no function @0x" + Long.toHexString(va) + ")");
            return;
        }
        println("==== decompile " + f.getName() + " @0x" + Long.toHexString(f.getEntryPoint().getOffset()) + " (cap " + cap + ") ====");
        try {
            DecompInterface dec = new DecompInterface();
            dec.openProgram(currentProgram);
            DecompileResults res = dec.decompileFunction(f, 60, monitor);
            if (res != null && res.decompileCompleted()) {
                String[] lines = res.getDecompiledFunction().getC().split("\n");
                for (int i = 0; i < Math.min(lines.length, cap); i++) {
                    println("  " + lines[i]);
                }
                if (lines.length > cap) {
                    println("  ... (" + (lines.length - cap) + " more lines)");
                }
            } else {
                println("  (decompile failed)");
            }
            dec.dispose();
        } catch (Exception e) {
            println("  (decompile error " + e + ")");
        }
    }

    void allRefs(long va, String label) {
        println("==== ALL refs to " + label + " (0x" + Long.toHexString(va) + ") ====");
        for (Reference r : getReferencesTo(toAddr(va))) {
            Function f = getFunctionContaining(r.getFromAddress());
            println("  " + r.getReferenceType() + " from " + r.getFromAddress()
                    + " in " + (f != null ? f.getName() + "@0x" + Long.toHexString(f.getEntryPoint().getOffset()) : "?"));
        }
    }

    @Override
    public void run() throws Exception {
        scanAddr(0x142814839L, "human_ai flag");
        scanAddr(0x1431146f9L, "debugtooltip flag");
        scanAddr(0x142814833L, "flag 833");
        scanAddr(0x142814830L, "settings block base 830");

        println("==== dump 0x142814820..0x1428148a0 ====");
        for (long a = 0x142814820L; a < 0x1428148a0L; a += 16) {
            StringBuilder hex = new StringBuilder();
            StringBuilder asc = new StringBuilder();
            for (int i = 0; i < 16; i++) {
                int b = getByte(toAddr(a + i)) & 0xff;
                hex.append(String.format("%02x ", b));
                asc.append(b >= 32 && b < 127 ? (char) b : '.');
            }
            println("  " + Long.toHexString(a) + ": " + hex + " |" + asc + "|");
        }

        decompileFn(0x14095b080L, 16);
        decompileFn(0x14095b100L, 16);
        decompileFn(0x14095b190L, 16);
        allRefs(0x1431146f9L, "debugtooltip flag");
        allRefs(0x142814836L, "flag 836");
        allRefs(0x142814834L, "flag 834");
        println("==== done ====");
    }
}
