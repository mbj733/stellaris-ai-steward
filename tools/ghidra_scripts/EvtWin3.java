// EvtWin3: 选项循环 FUN_14107d780 + 回调构造器头 + 数据表解析 + human_ai 轮询点
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public class EvtWin3 extends GhidraScript {

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
            DecompileResults res = dec.decompileFunction(f, 120, monitor);
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

    void asmAt(long va, int before, int after) {
        println("==== asm @0x" + Long.toHexString(va) + " ====");
        Address a = toAddr(va);
        Instruction ins = getInstructionAt(a);
        if (ins == null) {
            for (long probe = va - 0x60; probe <= va; probe += 1) {
                ins = getInstructionAt(toAddr(probe));
                if (ins != null && ins.getAddress().getOffset() <= va && va <= ins.getMaxAddress().getOffset()) {
                    break;
                }
                ins = null;
            }
        }
        if (ins == null) {
            println("  (no instruction)");
            return;
        }
        for (int i = 0; i < before; i++) {
            Instruction p = ins.getPrevious();
            if (p == null) {
                break;
            }
            ins = p;
        }
        for (int i = 0; i < before + after; i++) {
            println("   " + ins.getAddress() + "  " + ins);
            ins = ins.getNext();
            if (ins == null) {
                break;
            }
        }
    }

    void dumpTable(long start, int words) {
        println("==== table @0x" + Long.toHexString(start) + " (" + words + " qwords) ====");
        for (int i = 0; i < words; i++) {
            long a = start + 8L * i;
            try {
                long v = getLong(toAddr(a));
                String extra = "";
                if (v >= 0x140000000L && v < 0x150000000L) {
                    Function f = getFunctionContaining(toAddr(v));
                    if (f != null && f.getEntryPoint().getOffset() == v) {
                        extra = "  -> " + f.getName();
                    } else if (f != null) {
                        extra = "  -> inside " + f.getName();
                    } else {
                        extra = "  -> ?";
                    }
                }
                println(String.format("  @0x%x : 0x%x%s", a, v, extra));
            } catch (Exception e) {
                println("  @0x" + Long.toHexString(a) + " : (unreadable)");
            }
        }
    }

    @Override
    public void run() throws Exception {
        allRefs(0x14107d780L, "FUN_14107d780 option loop");
        decompileFn(0x14107d780L, 150);

        println("==== FUN_1407b5a10 head ====");
        decompileFn(0x1407b5a10L, 40);

        dumpTable(0x1436a2b80L, 16);
        dumpTable(0x1436b0260L, 12);

        // human_ai 轮询点
        allRefs(0x140a98c80L, "FUN_140a98c80 (reads human_ai flag)");
        decompileFn(0x140a98c80L, 110);

        // 写点（未命名函数区）看上下文
        asmAt(0x140959f14L, 10, 12);
        asmAt(0x14095a074L, 10, 12);

        println("==== done ====");
    }
}
